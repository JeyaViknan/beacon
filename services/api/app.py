"""API Lambda (HANDOVER §9) behind CloudFront ``/api/*`` via a Function URL.

Every request must carry ``X-Beacon-Origin`` (added by CloudFront), so calling the Function URL
directly gets 403. Everything except ``/api/health`` and ``/api/auth/login`` needs a Bearer JWT.
Errors always look like ``{"error": {"code", "message"}}``.
"""

import asyncio
import hashlib
import json
import os
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import LambdaFunctionUrlResolver, Response
from aws_lambda_powertools.event_handler.middlewares import NextMiddleware
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ulid import ULID

from beacon_core import VERSION, aws
from beacon_core.alerts import (
    acknowledged_alert,
    make_test_alert,
    recovered_alert,
    sns_publish_kwargs,
)
from beacon_core.auth import (
    AuthError,
    Throttle,
    bearer_token,
    issue_token,
    same_secret,
    verify_password,
    verify_token,
)
from beacon_core.checks import new_client, run_check
from beacon_core.models import (
    Alert,
    Incident,
    IncidentState,
    MonitorSpec,
    Product,
    ProductInput,
    Settings,
)
from beacon_core.repo_dynamo import ConflictError, Repo
from beacon_core.ssrf import DNSError, Resolver, SSRFError, system_resolver, validate_url
from beacon_core.state_machine import (
    IncidentResolved,
    acknowledge,
    parse_incident_sk,
    pause,
    resume,
)
from beacon_core.timeutil import to_iso, utc_now
from beacon_core.views import (
    Range,
    product_detail,
    product_summary,
    public_product,
    series_keys,
    series_points,
    sort_summaries,
    summary_counts,
    window_bounds,
)

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = LambdaFunctionUrlResolver()

PUBLIC_ROUTES = {("GET", "/api/health"), ("POST", "/api/auth/login")}
DEMO_PARAM = "/beacon/demo/healthy"
PUSH_HOST_SUFFIXES = (
    "push.apple.com",
    "googleapis.com",
    "push.services.mozilla.com",
    "notify.windows.com",
)
RESOLVER: Resolver = system_resolver


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}


def json_response(status: int, body: Any, headers: dict[str, str] | None = None) -> Response:
    return Response(
        status_code=status,
        content_type="application/json",
        body=json.dumps(body) if body is not None else "",
        headers={"cache-control": "no-store", **(headers or {})},
    )


def error_response(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> Response:
    return json_response(status, {"error": {"code": code, "message": message}}, headers)


@app.exception_handler(ApiError)
def _api_error(exc: ApiError) -> Response:
    return error_response(exc.status, exc.code, exc.message, exc.headers)


@app.exception_handler(ValidationError)
def _validation_error(exc: ValidationError) -> Response:
    first = exc.errors()[0] if exc.errors() else {"msg": "invalid input", "loc": ()}
    where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    message = f"{where}: {first['msg']}" if where else str(first["msg"])
    return error_response(422, "validation_error", message)


@app.not_found
def _not_found(_: Exception) -> Response:
    return error_response(404, "not_found", "no such route")


# ------------------------------------------------------------------------------ middleware


def guard(app: LambdaFunctionUrlResolver, next_middleware: NextMiddleware) -> Response:
    event = app.current_event
    expected = os.environ.get("ORIGIN_VERIFY_SECRET", "")
    if not same_secret(expected, event.headers.get("x-beacon-origin")):
        return error_response(403, "forbidden", "requests must come through CloudFront")
    if (event.http_method.upper(), event.path) not in PUBLIC_ROUTES:
        secret = aws.param("/beacon/jwt_secret")
        if not secret:
            return error_response(503, "not_configured", "JWT secret is not set")
        try:
            verify_token(secret, bearer_token(event.headers.get("authorization")), utc_now())
        except AuthError as exc:
            return error_response(401, "unauthorized", str(exc))
    response = next_middleware(app)
    response.headers.setdefault("cache-control", "no-store")  # API responses are never cached
    return response


app.use(middlewares=[guard])


# ------------------------------------------------------------------------------ helpers


def repo() -> Repo:
    return aws.repo()


def body() -> dict[str, Any]:
    try:
        data = app.current_event.json_body
    except (json.JSONDecodeError, TypeError) as exc:
        raise ApiError(400, "bad_request", "body must be JSON") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ApiError(400, "bad_request", "body must be a JSON object")
    return data


def query_int(name: str, default: int, low: int, high: int) -> int:
    raw = app.current_event.get_query_string_value(name, str(default)) or str(default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ApiError(400, "bad_request", f"{name} must be an integer") from exc
    return max(low, min(high, value))


def load_product(product_id: str) -> Product:
    product = repo().get_product(product_id)
    if product is None:
        raise ApiError(404, "not_found", "product not found")
    return product


def check_url_allowed(url: str) -> None:
    """Same SSRF rules as the probe. An unresolvable host is allowed (the probe will report it)."""
    try:
        asyncio.run(validate_url(url, RESOLVER))
    except DNSError:
        return
    except SSRFError as exc:
        raise ApiError(422, "url_not_allowed", str(exc)) from exc


def publish(alert: Alert) -> None:
    topic = os.environ.get("PRODUCT_ALERTS_TOPIC_ARN")
    if not topic:
        raise ApiError(503, "not_configured", "alerts topic is not configured")
    aws.sns().publish(**sns_publish_kwargs(alert, topic, os.environ.get("APP_URL")))


def republish_snapshot(changed: Product | None = None, deleted_id: str | None = None) -> None:
    repo().publish_snapshot(utc_now(), changed=changed, deleted_id=deleted_id)


def resolve_open_incident(product: Product, resolved: IncidentResolved) -> None:
    repo().resolve_incident(
        product.id, resolved.sk, resolved.resolved_at, resolved.duration_sec, resolved.cause
    )
    publish(recovered_alert(product, resolved))


# ------------------------------------------------------------------------------ health + auth


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": VERSION, "time": to_iso(utc_now())}


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=256)


@app.post("/api/auth/login")
def login() -> Response:
    data = LoginIn.model_validate(body())
    now = utc_now()
    throttle = Throttle.from_item(repo().get_throttle())
    wait = throttle.retry_after(now)
    if wait > 0:
        raise ApiError(
            429,
            "locked",
            f"too many failed logins; try again in {wait // 60 + 1} min",
            {"retry-after": str(wait)},
        )
    stored_hash = aws.param("/beacon/admin_password_hash")
    secret = aws.param("/beacon/jwt_secret")
    if not stored_hash or not secret:
        raise ApiError(503, "not_configured", "admin password or JWT secret is not set")
    if not verify_password(stored_hash, data.password):
        after = throttle.after_failure(now)
        repo().put_throttle(after.failures, after.locked_until, now)
        logger.warning("Failed login", extra={"failures": after.failures})
        raise ApiError(401, "wrong_password", "wrong password")
    if throttle.failures:
        repo().clear_throttle()
    token, expires_at = issue_token(secret, now)
    return json_response(200, {"token": token, "expiresAt": expires_at})


# ------------------------------------------------------------------------------ products


@app.get("/api/summary")
def summary() -> dict[str, Any]:
    return summary_counts(repo().list_products())


@app.get("/api/products")
def list_products() -> list[dict[str, Any]]:
    kind = app.current_event.get_query_string_value("kind", None)
    now = utc_now()
    bounds = window_bounds(now)
    out = []
    for product in repo().list_products():
        if kind and product.kind != kind:
            continue
        rd = repo().rollups(product.id, *bounds["rd"])
        rh = repo().rollups(product.id, *bounds["rh24"])
        out.append(product_summary(product, rd, rh, now))
    return sort_summaries(out)


@app.post("/api/products")
def create_product() -> Response:
    config = ProductInput.model_validate(body())
    check_url_allowed(config.check_url)
    now = utc_now()
    product = Product.model_validate(
        {
            **config.model_dump(),
            "id": str(ULID()),
            "enabled": True,
            "createdAt": to_iso(now),
            "updatedAt": to_iso(now),
            "statusSince": to_iso(now),
        }
    )
    repo().create_product(product)
    republish_snapshot(changed=product)
    logger.info("Product created", extra={"product_id": product.id})
    return json_response(201, public_product(product))


@app.get("/api/products/<product_id>")
def get_product(product_id: str) -> dict[str, Any]:
    product = load_product(product_id)
    bounds = window_bounds(utc_now())
    r = repo()
    open_incident = (
        r.get_incident(product.id, product.open_incident_sk) if product.open_incident_sk else None
    )
    return product_detail(
        product,
        r5=r.rollups(product.id, *bounds["r5"]),
        rh=r.rollups(product.id, *bounds["rh"]),
        rd=r.rollups(product.id, *bounds["rd"]),
        open_incident=open_incident,
    )


@app.patch("/api/products/<product_id>")
def update_product(product_id: str) -> dict[str, Any]:
    product = load_product(product_id)
    current = product.config().model_dump()
    config = ProductInput.model_validate({**current, **body()})
    if config.check_url != product.check_url:
        check_url_allowed(config.check_url)
    try:
        updated = repo().update_config(product, config, utc_now())
    except ConflictError as exc:
        raise ApiError(409, "conflict", "product changed meanwhile; reload and retry") from exc
    republish_snapshot(changed=updated)
    return public_product(updated)


@app.delete("/api/products/<product_id>")
def delete_product(product_id: str) -> Response:
    product = load_product(product_id)
    if product.open_incident_sk:
        _, resolved = pause(product, utc_now())
        if resolved is not None:
            resolve_open_incident(
                product,
                IncidentResolved(
                    resolved.sk, resolved.resolved_at, resolved.duration_sec, "product deleted"
                ),
            )
    repo().delete_product(product.id)
    republish_snapshot(deleted_id=product.id)
    logger.info("Product deleted", extra={"product_id": product.id})
    return json_response(204, None)


@app.post("/api/products/<product_id>/pause")
def pause_product(product_id: str) -> dict[str, Any]:
    product = load_product(product_id)
    if not product.enabled:
        return public_product(product)
    now = utc_now()
    state, resolved = pause(product, now)
    try:
        updated = repo().update_live(product, state, now, enabled=False)
    except ConflictError as exc:
        raise ApiError(409, "conflict", "product changed meanwhile; retry") from exc
    if resolved is not None:
        resolve_open_incident(updated, resolved)
    republish_snapshot(changed=updated)
    return public_product(updated)


@app.post("/api/products/<product_id>/resume")
def resume_product(product_id: str) -> dict[str, Any]:
    product = load_product(product_id)
    if product.enabled:
        return public_product(product)
    now = utc_now()
    try:
        updated = repo().update_live(product, resume(product, now), now, enabled=True)
    except ConflictError as exc:
        raise ApiError(409, "conflict", "product changed meanwhile; retry") from exc
    republish_snapshot(changed=updated)
    return public_product(updated)


@app.post("/api/products/<product_id>/test")
def test_product(product_id: str) -> dict[str, Any]:
    """Run a check right now from the API Lambda. Stored as manual; never counts toward uptime."""
    product = load_product(product_id)
    spec = MonitorSpec.model_validate(product.config().model_dump() | {"id": product.id})

    async def go() -> Any:
        async with new_client() as client:
            return await run_check(client, spec, resolver=RESOLVER)

    now = utc_now()
    result = asyncio.run(go())
    region = os.environ.get("AWS_REGION", "unknown")
    repo().put_manual_check(product.id, region, result, now)
    return {**result.model_dump(mode="json"), "checkedAt": to_iso(now), "region": region}


@app.get("/api/products/<product_id>/series")
def product_series(product_id: str) -> dict[str, Any]:
    load_product(product_id)
    raw = app.current_event.get_query_string_value("range", "24h") or "24h"
    if raw not in ("24h", "7d", "30d"):
        raise ApiError(400, "bad_request", "range must be 24h, 7d or 30d")
    rng: Range = raw  # type: ignore[assignment]
    now = utc_now()
    keys = series_keys(rng, now)
    buckets = repo().rollups(product_id, keys[0][0], keys[-1][0])
    return {"range": rng, "points": series_points(rng, buckets, now)}


@app.get("/api/products/<product_id>/checks")
def product_checks(product_id: str) -> list[dict[str, Any]]:
    load_product(product_id)
    return repo().recent_checks(product_id, query_int("limit", 20, 1, 100))


@app.get("/api/products/<product_id>/incidents")
def product_incidents(product_id: str) -> list[dict[str, Any]]:
    load_product(product_id)
    limit = query_int("limit", 20, 1, 100)
    return [i.model_dump(mode="json") for i in repo().incidents_for(product_id, limit)]


def find_incident(product_id: str, ref: str) -> Incident:
    ref = unquote(ref)
    if ref.startswith("INC#"):
        try:
            parse_incident_sk(ref)
        except ValueError as exc:
            raise ApiError(400, "bad_request", "invalid incident key") from exc
        incident = repo().get_incident(product_id, ref)
    else:
        incident = repo().find_incident(product_id, ref)
    if incident is None:
        raise ApiError(404, "not_found", "incident not found")
    return incident


@app.post("/api/products/<product_id>/incidents/<ref>/ack")
def ack_incident(product_id: str, ref: str) -> dict[str, Any]:
    incident = find_incident(product_id, ref)
    if incident.state is IncidentState.ACKNOWLEDGED:
        return incident.model_dump(mode="json")
    try:
        acked = acknowledge(incident, utc_now())
        repo().save_acknowledged(acked)
    except (ValueError, ConflictError) as exc:
        raise ApiError(409, "conflict", "incident is already resolved") from exc
    publish(acknowledged_alert(acked))
    logger.info("Incident acknowledged", extra={"product_id": product_id})
    return acked.model_dump(mode="json")


@app.get("/api/incidents")
def incidents_feed() -> list[dict[str, Any]]:
    state = app.current_event.get_query_string_value("state", "all") or "all"
    if state not in ("open", "all"):
        raise ApiError(400, "bad_request", "state must be open or all")
    limit = query_int("limit", 50, 1, 200)
    return [
        i.model_dump(mode="json")
        for i in repo().incidents_feed(open_only=state == "open", limit=limit)
    ]


# ---------------------------------------------------------------------- push + notifications


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class PushSubscriptionIn(BaseModel):
    """The browser's ``PushSubscription.toJSON()``; ``expirationTime`` is accepted and ignored."""

    model_config = ConfigDict(extra="ignore")
    endpoint: str = Field(max_length=2048)
    keys: PushKeys


def push_endpoint_allowed(endpoint: str) -> bool:
    """Only real push services: the notifier POSTs to this URL, so it must not be an SSRF hole."""
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(
        host == s or host.endswith("." + s) for s in PUSH_HOST_SUFFIXES
    )


def endpoint_key(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()


@app.post("/api/push/subscriptions")
def add_subscription() -> Response:
    sub = PushSubscriptionIn.model_validate(body())
    if not push_endpoint_allowed(sub.endpoint):
        raise ApiError(422, "endpoint_not_allowed", "not a known Web Push service endpoint")
    repo().put_subscription(
        endpoint_key(sub.endpoint),
        {
            "endpoint": sub.endpoint,
            "keys": sub.keys.model_dump(),
            "ua": (app.current_event.headers.get("user-agent") or "")[:200],
            "createdAt": to_iso(utc_now()),
        },
    )
    return json_response(201, {"subscribed": True})


@app.delete("/api/push/subscriptions")
def remove_subscription() -> Response:
    endpoint = body().get("endpoint")
    if not isinstance(endpoint, str) or not endpoint:
        raise ApiError(400, "bad_request", "endpoint is required")
    repo().delete_subscription(endpoint_key(endpoint))
    return json_response(204, None)


@app.post("/api/notifications/test")
def test_notification() -> Response:
    publish(make_test_alert())
    return json_response(202, {"queued": True})


def set_demo(healthy: bool) -> dict[str, Any]:
    aws.ssm().put_parameter(
        Name=DEMO_PARAM, Value="true" if healthy else "false", Type="String", Overwrite=True
    )
    logger.info("Demo target toggled", extra={"healthy": healthy})
    return {"healthy": healthy}


@app.post("/api/demo/break")
def demo_break() -> dict[str, Any]:
    return set_demo(False)


@app.post("/api/demo/fix")
def demo_fix() -> dict[str, Any]:
    return set_demo(True)


# ------------------------------------------------------------------------------ settings


def channel_status() -> dict[str, Any]:
    return {
        "pushDevices": len(repo().list_subscriptions()),
        "email": os.environ.get("EMAIL_CONFIGURED", "false") == "true",
        "pagerduty": aws.param("/beacon/pagerduty_routing_key") is not None,
        "vapid": aws.param("/beacon/vapid_private_key") is not None,
        "healthchecks": aws.param("/beacon/healthchecks_ping_url") is not None,
    }


def demo_state() -> Literal["healthy", "broken"]:
    value = aws.param(DEMO_PARAM, max_age=0) or "true"
    return "broken" if value.lower() == "false" else "healthy"


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return {
        "settings": repo().get_settings().model_dump(mode="json"),
        "channels": channel_status(),
        "demo": demo_state(),
        "version": VERSION,
        "region": os.environ.get("AWS_REGION"),
    }


@app.patch("/api/settings")
def patch_settings() -> dict[str, Any]:
    raw = body()
    unknown = set(raw) - {"quorum", "pushEnabled", "emailEnabled", "pagerdutyEnabled"}
    if unknown:
        raise ApiError(422, "validation_error", f"unknown settings: {', '.join(sorted(unknown))}")
    current = repo().get_settings().model_dump()
    settings = Settings.model_validate({**current, **raw})
    repo().put_settings(settings)
    return settings.model_dump(mode="json")


# ------------------------------------------------------------------------------ entry point


@logger.inject_lambda_context(correlation_id_path=correlation_paths.LAMBDA_FUNCTION_URL)
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    return app.resolve(event, context)
