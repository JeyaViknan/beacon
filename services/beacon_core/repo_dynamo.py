"""All DynamoDB access for the single ``beacon`` table (HANDOVER §7).

The processor's write path is one ``TransactWriteItems`` per result (ADR 0011): raw check
(conditional put, the idempotency key), product live state (optimistic lock on ``version``),
the three rollups (``ADD``) and the incident. Either all of it lands or none of it does, so a
redelivered SQS message is detected as a duplicate instead of double-counting.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from beacon_core.ddb import Update, from_ddb, to_ddb, without_none
from beacon_core.models import (
    CheckResult,
    Incident,
    IncidentState,
    LiveState,
    Product,
    ProductInput,
    Settings,
)
from beacon_core.snapshot import SNAPSHOT_KEY, build_snapshot
from beacon_core.state_machine import Evaluation, new_incident
from beacon_core.timeutil import r5_key, rd_key, rh_key, to_iso, ttl_after
from beacon_core.uptime import Rollup

CHECK_TTL_H = 48
R5_TTL_H = 48
RH_TTL_H = 8 * 24
RD_TTL_H = 400 * 24
THROTTLE_TTL_H = 0.25

SETTINGS_KEY = {"PK": "CONFIG", "SK": "SETTINGS"}
THROTTLE_KEY = {"PK": "AUTH", "SK": "THROTTLE"}
PUSHSUB_PK = "PUSHSUB"


class ConflictError(Exception):
    """Optimistic-lock conflict: someone else wrote the product first."""


class DuplicateError(Exception):
    """The raw check for (product, region, runAt) already exists: this result was applied."""


def product_key(product_id: str) -> dict[str, str]:
    return {"PK": f"PRODUCT#{product_id}", "SK": "META"}


def product_gsi1sk(sort_order: int, name: str) -> str:
    return f"{sort_order:05d}#{name.lower()}"


def check_sk(run_at_iso: str, region: str, *, manual: bool = False) -> str:
    return f"CHECK#{run_at_iso}#{region}" + ("#manual" if manual else "")


def _is_conditional_failure(err: ClientError) -> bool:
    return err.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


@dataclass(frozen=True)
class ApplyResult:
    applied: bool
    incident: Incident | None = None


class Repo:
    def __init__(self, table: Any) -> None:
        self.table = table
        self.client = table.meta.client

    # ------------------------------------------------------------------ products

    def get_product(self, product_id: str) -> Product | None:
        item = self.table.get_item(Key=product_key(product_id), ConsistentRead=True).get("Item")
        return Product.model_validate(from_ddb(item)) if item else None

    def list_products(self) -> list[Product]:
        items = self._query_all(
            IndexName="GSI1", KeyConditionExpression=Key("GSI1PK").eq("PRODUCTS")
        )
        return [Product.model_validate(from_ddb(i)) for i in items]

    def _product_item(self, product: Product) -> dict[str, Any]:
        item = without_none(product.model_dump(mode="json"))
        item.update(
            product_key(product.id)
            | {"GSI1PK": "PRODUCTS", "GSI1SK": product_gsi1sk(product.sort_order, product.name)}
        )
        return to_ddb(item)

    def create_product(self, product: Product) -> None:
        self.table.put_item(
            Item=self._product_item(product), ConditionExpression=Attr("PK").not_exists()
        )

    def update_config(self, product: Product, config: ProductInput, now: datetime) -> Product:
        """Replace the user-editable fields; optimistic lock on ``version``."""
        fields = config.model_dump(mode="json")
        upd = Update().set_many(fields)
        upd.set("updatedAt", to_iso(now))
        upd.set("GSI1SK", product_gsi1sk(config.sort_order, config.name))
        upd.set("version", product.version + 1)
        self._conditional_update(product, upd)
        return product.model_copy(
            update={**dict(config), "updated_at": to_iso(now), "version": product.version + 1}
        )

    def update_live(
        self, product: Product, state: LiveState, now: datetime, *, enabled: bool | None = None
    ) -> Product:
        upd = Update().set_many(state.model_dump(mode="json"))
        upd.set("updatedAt", to_iso(now))
        upd.set("version", product.version + 1)
        extra: dict[str, Any] = {}
        if enabled is not None:
            upd.set("enabled", enabled)
            extra["enabled"] = enabled
        self._conditional_update(product, upd)
        return product.model_copy(
            update={
                **dict(state),
                **extra,
                "updated_at": to_iso(now),
                "version": product.version + 1,
            }
        )

    def _conditional_update(self, product: Product, upd: Update) -> None:
        cond = f"{upd.name('version')} = {upd.value(product.version)}"
        try:
            self.table.update_item(Key=product_key(product.id), **upd.kwargs(cond))
        except ClientError as err:
            if _is_conditional_failure(err):
                raise ConflictError(product.id) from err
            raise

    def delete_product(self, product_id: str) -> bool:
        try:
            self.table.delete_item(
                Key=product_key(product_id), ConditionExpression=Attr("PK").exists()
            )
        except ClientError as err:
            if _is_conditional_failure(err):
                return False
            raise
        return True

    # ------------------------------------------------------------------ snapshot

    def publish_snapshot(
        self, now: datetime, *, changed: Product | None = None, deleted_id: str | None = None
    ) -> int:
        """Rebuild ``CONFIG/MONITORS``.

        GSI reads are eventually consistent, so the product that was just written is merged in
        explicitly; otherwise a brand-new product could be missing from the snapshot.
        """
        products = {p.id: p for p in self.list_products()}
        if changed is not None:
            products[changed.id] = changed
        if deleted_id is not None:
            products.pop(deleted_id, None)
        version = int(now.timestamp() * 1000)
        snapshot = build_snapshot(products.values(), version, now)
        self.table.put_item(Item=to_ddb({**SNAPSHOT_KEY, **snapshot.model_dump(mode="json")}))
        return version

    def get_snapshot_item(self) -> dict[str, Any] | None:
        item: dict[str, Any] | None = self.table.get_item(Key=SNAPSHOT_KEY).get("Item")
        return item

    # ------------------------------------------------------------------ processor write path

    def apply_evaluation(
        self,
        product: Product,
        region: str,
        result: CheckResult,
        run_at: datetime,
        evaluation: Evaluation,
    ) -> ApplyResult:
        """Write one evaluated result atomically. Raises ``DuplicateError``/``ConflictError``.

        ``self.client`` is the resource's client, which serialises plain Python values itself,
        so items here are native values (Decimal for numbers), not ``{"S": ...}`` wire format.
        """
        run_iso = to_iso(run_at)
        pk = f"PRODUCT#{product.id}"
        table = self.table.name
        items: list[dict[str, Any]] = []

        check_item = without_none(
            {
                "PK": pk,
                "SK": check_sk(run_iso, region),
                "at": run_iso,
                "region": region,
                "ok": result.ok,
                "httpCode": result.http_code,
                "latencyMs": result.latency_ms,
                "error": result.error,
                "manual": False,
                "ttl": ttl_after(run_at, hours=CHECK_TTL_H),
            }
        )
        items.append(
            {
                "Put": {
                    "TableName": table,
                    "Item": to_ddb(check_item),
                    "ConditionExpression": "attribute_not_exists(SK)",
                }
            }
        )

        live = Update().set_many(evaluation.state.model_dump(mode="json"))
        live.set("version", product.version + 1)
        cond = f"{live.name('version')} = {live.value(product.version)}"
        items.append(
            {
                "Update": {
                    "TableName": table,
                    "Key": product_key(product.id),
                    "UpdateExpression": live.expression,
                    "ConditionExpression": cond,
                    "ExpressionAttributeNames": live.names,
                    "ExpressionAttributeValues": live.values,
                }
            }
        )

        has_latency = result.ok and result.latency_ms is not None
        delta = evaluation.rollup
        if has_latency or delta.total_min or delta.up_min or delta.down_min:
            for sk, hours in (
                (r5_key(run_at), R5_TTL_H),
                (rh_key(run_at), RH_TTL_H),
                (rd_key(run_at), RD_TTL_H),
            ):
                upd = Update()
                upd.add("upMin", delta.up_min).add("totalMin", delta.total_min)
                upd.add("downMin", delta.down_min)
                if has_latency:
                    upd.add("latSum", result.latency_ms or 0).add("latCount", 1)
                upd.set("ttl", ttl_after(run_at, hours=hours))
                items.append(
                    {
                        "Update": {
                            "TableName": table,
                            "Key": {"PK": pk, "SK": sk},
                            "UpdateExpression": upd.expression,
                            "ExpressionAttributeNames": upd.names,
                            "ExpressionAttributeValues": upd.values,
                        }
                    }
                )

        incident: Incident | None = None
        if evaluation.opened is not None:
            incident = new_incident(product, evaluation.opened)
            items.append(
                {
                    "Put": {
                        "TableName": table,
                        "Item": self._incident_item(incident),
                        "ConditionExpression": "attribute_not_exists(SK)",
                    }
                }
            )
        if evaluation.resolved is not None:
            res = evaluation.resolved
            upd = Update()
            upd.set("state", IncidentState.RESOLVED.value)
            upd.set("resolvedAt", res.resolved_at).set("durationSec", res.duration_sec)
            upd.append(
                "timeline", [{"at": res.resolved_at, "event": "resolved", "detail": res.cause}]
            )
            items.append(
                {
                    "Update": {
                        "TableName": table,
                        "Key": {"PK": pk, "SK": res.sk},
                        "UpdateExpression": upd.expression,
                        "ExpressionAttributeNames": upd.names,
                        "ExpressionAttributeValues": upd.values,
                    }
                }
            )

        try:
            self.client.transact_write_items(TransactItems=items)
        except ClientError as err:
            if err.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                raise
            reasons = err.response.get("CancellationReasons") or []
            codes = [r.get("Code") for r in reasons]
            if codes and codes[0] == "ConditionalCheckFailed":
                raise DuplicateError(check_item["SK"]) from err
            if len(codes) > 1 and codes[1] == "ConditionalCheckFailed":
                raise ConflictError(product.id) from err
            raise

        if has_latency:
            self._raise_lat_max(pk, run_at, result.latency_ms or 0)
        if incident is None and evaluation.resolved is not None:
            incident = self.get_incident(product.id, evaluation.resolved.sk)
        return ApplyResult(applied=True, incident=incident)

    def _raise_lat_max(self, pk: str, run_at: datetime, latency: int) -> None:
        """``latMax = max(latMax, latency)``. DynamoDB has no MAX, so use a conditional SET."""
        for sk in (r5_key(run_at), rh_key(run_at), rd_key(run_at)):
            try:
                self.table.update_item(
                    Key={"PK": pk, "SK": sk},
                    UpdateExpression="SET latMax = :v",
                    ConditionExpression="attribute_not_exists(latMax) OR latMax < :v",
                    ExpressionAttributeValues={":v": latency},
                )
            except ClientError as err:
                if not _is_conditional_failure(err):
                    raise

    # ------------------------------------------------------------------ checks and rollups

    def put_manual_check(
        self, product_id: str, region: str, result: CheckResult, at: datetime
    ) -> None:
        iso = to_iso(at)
        item = without_none(
            {
                "PK": f"PRODUCT#{product_id}",
                "SK": check_sk(iso, region, manual=True),
                "at": iso,
                "region": region,
                "ok": result.ok,
                "httpCode": result.http_code,
                "latencyMs": result.latency_ms,
                "error": result.error,
                "manual": True,
                "ttl": ttl_after(at, hours=CHECK_TTL_H),
            }
        )
        self.table.put_item(Item=to_ddb(item))

    def recent_checks(self, product_id: str, limit: int = 20) -> list[dict[str, Any]]:
        resp = self.table.query(
            KeyConditionExpression=Key("PK").eq(f"PRODUCT#{product_id}")
            & Key("SK").begins_with("CHECK#"),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [
            {k: v for k, v in from_ddb(i).items() if k not in ("PK", "SK", "ttl")}
            for i in resp.get("Items", [])
        ]

    def rollups(self, product_id: str, first_key: str, last_key: str) -> dict[str, Rollup]:
        items = self._query_all(
            KeyConditionExpression=Key("PK").eq(f"PRODUCT#{product_id}")
            & Key("SK").between(first_key, last_key)
        )
        return {i["SK"]: Rollup.from_item(i) for i in items}

    # ------------------------------------------------------------------ incidents

    @staticmethod
    def _incident_item(incident: Incident) -> dict[str, Any]:
        item = without_none(incident.model_dump(mode="json"))
        item.update(
            {
                "PK": f"PRODUCT#{incident.product_id}",
                "SK": incident.sk,
                "GSI1PK": "INCIDENTS",
                "GSI1SK": f"{incident.started_at}#{incident.id}",
            }
        )
        return to_ddb(item)

    @staticmethod
    def _incident(item: dict[str, Any]) -> Incident:
        return Incident.model_validate(from_ddb(item))

    def get_incident(self, product_id: str, sk: str) -> Incident | None:
        item = self.table.get_item(
            Key={"PK": f"PRODUCT#{product_id}", "SK": sk}, ConsistentRead=True
        ).get("Item")
        return self._incident(item) if item else None

    def find_incident(self, product_id: str, incident_id: str) -> Incident | None:
        for inc in self.incidents_for(product_id, limit=100):
            if inc.id == incident_id:
                return inc
        return None

    def incidents_for(self, product_id: str, limit: int = 20) -> list[Incident]:
        resp = self.table.query(
            KeyConditionExpression=Key("PK").eq(f"PRODUCT#{product_id}")
            & Key("SK").begins_with("INC#"),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [self._incident(i) for i in resp.get("Items", [])]

    def incidents_feed(self, *, open_only: bool, limit: int = 50) -> list[Incident]:
        kwargs: dict[str, Any] = {
            "IndexName": "GSI1",
            "KeyConditionExpression": Key("GSI1PK").eq("INCIDENTS"),
            "ScanIndexForward": False,
        }
        if open_only:
            kwargs["FilterExpression"] = Attr("state").ne(IncidentState.RESOLVED.value)
        out: list[Incident] = []
        for item in self._query_iter(**kwargs):
            out.append(self._incident(item))
            if len(out) >= limit:
                break
        return out

    def incidents_between(self, start_iso: str, end_iso: str) -> list[Incident]:
        items = self._query_all(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq("INCIDENTS")
            & Key("GSI1SK").between(start_iso, end_iso),
        )
        return [self._incident(i) for i in items]

    def save_acknowledged(self, incident: Incident) -> None:
        """Persist an acknowledgement; refuses if the incident was resolved meanwhile."""
        upd = Update()
        upd.set("state", IncidentState.ACKNOWLEDGED.value).set(
            "acknowledgedAt", incident.acknowledged_at
        )
        upd.append("timeline", [incident.timeline[-1].model_dump(mode="json")])
        cond = f"{upd.name('state')} = {upd.value(IncidentState.OPEN.value)}"
        try:
            self.table.update_item(
                Key={"PK": f"PRODUCT#{incident.product_id}", "SK": incident.sk},
                **upd.kwargs(cond),
            )
        except ClientError as err:
            if _is_conditional_failure(err):
                raise ConflictError(incident.sk) from err
            raise

    def resolve_incident(
        self, product_id: str, sk: str, resolved_at: str, duration: int, cause: str
    ) -> None:
        upd = Update()
        upd.set("state", IncidentState.RESOLVED.value)
        upd.set("resolvedAt", resolved_at).set("durationSec", duration)
        upd.append("timeline", [{"at": resolved_at, "event": "resolved", "detail": cause}])
        self.table.update_item(Key={"PK": f"PRODUCT#{product_id}", "SK": sk}, **upd.kwargs())

    # ------------------------------------------------------------------ push subscriptions

    def put_subscription(self, key: str, subscription: dict[str, Any]) -> None:
        self.table.put_item(Item=to_ddb({"PK": PUSHSUB_PK, "SK": key, **subscription}))

    def delete_subscription(self, key: str) -> None:
        self.table.delete_item(Key={"PK": PUSHSUB_PK, "SK": key})

    def list_subscriptions(self) -> list[dict[str, Any]]:
        items = self._query_all(KeyConditionExpression=Key("PK").eq(PUSHSUB_PK))
        return [from_ddb(i) for i in items]

    # ------------------------------------------------------------------ settings and auth

    def get_settings(self) -> Settings:
        item = self.table.get_item(Key=SETTINGS_KEY).get("Item")
        return Settings.model_validate(from_ddb(item)) if item else Settings()

    def put_settings(self, settings: Settings) -> None:
        self.table.put_item(Item=to_ddb({**SETTINGS_KEY, **settings.model_dump(mode="json")}))

    def get_throttle(self) -> dict[str, Any]:
        item = self.table.get_item(Key=THROTTLE_KEY, ConsistentRead=True).get("Item")
        return from_ddb(item) if item else {}

    def put_throttle(self, failures: int, locked_until: str | None, now: datetime) -> None:
        item = without_none(
            {
                **THROTTLE_KEY,
                "failures": failures,
                "lockedUntil": locked_until,
                "ttl": ttl_after(now, hours=THROTTLE_TTL_H),
            }
        )
        self.table.put_item(Item=to_ddb(item))

    def clear_throttle(self) -> None:
        self.table.delete_item(Key=THROTTLE_KEY)

    # ------------------------------------------------------------------ helpers

    def _query_iter(self, **kwargs: Any) -> Iterable[dict[str, Any]]:
        while True:
            resp = self.table.query(**kwargs)
            yield from resp.get("Items", [])
            if "LastEvaluatedKey" not in resp:
                return
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def _query_all(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list(self._query_iter(**kwargs))
