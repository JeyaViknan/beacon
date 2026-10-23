"""API routes through Lambda Function URL events (moto + respx)."""

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
import respx

from api import app as api
from beacon_core.auth import hash_password, issue_token
from beacon_core.models import Product
from beacon_core.repo_dynamo import Repo
from beacon_core.snapshot import SNAPSHOT_KEY
from beacon_core.state_machine import incident_sk
from beacon_core.timeutil import utc_now
from tests.conftest import product_item

ORIGIN = "origin-secret"
JWT_SECRET = "jwt-secret-for-tests-only-0123456789abcdef"
PASSWORD = "correct horse battery staple"
IP = "93.184.216.34"


async def fake_resolver(host: str, port: int) -> list[str]:
    table = {"nankiv.example": [IP], "internal.example": ["10.0.0.7"]}
    if host not in table:
        raise OSError("nxdomain")
    return table[host]


@pytest.fixture(scope="module")
def password_hash() -> str:
    return hash_password(PASSWORD)


@pytest.fixture
def env(aws, monkeypatch, password_hash):
    monkeypatch.setenv("ORIGIN_VERIFY_SECRET", ORIGIN)
    monkeypatch.setenv("EMAIL_CONFIGURED", "true")
    monkeypatch.setattr(api, "RESOLVER", fake_resolver)
    aws.set_param("/beacon/jwt_secret", JWT_SECRET)
    aws.set_param("/beacon/admin_password_hash", password_hash)
    return aws


@pytest.fixture
def token() -> str:
    return issue_token(JWT_SECRET, utc_now())[0]


def call(
    method: str,
    path: str,
    *,
    body: object = None,
    token: str | None = None,
    query: dict[str, str] | None = None,
    origin: str | None = ORIGIN,
    headers: dict[str, str] | None = None,
    context=None,
) -> tuple[int, object, dict]:
    hdrs = {"content-type": "application/json", "user-agent": "pytest"}
    if origin is not None:
        hdrs["x-beacon-origin"] = origin
    if token:
        hdrs["authorization"] = f"Bearer {token}"
    hdrs.update(headers or {})
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "&".join(f"{k}={v}" for k, v in (query or {}).items()),
        "headers": hdrs,
        "queryStringParameters": query,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "fnurl",
            "domainName": "fnurl.lambda-url.ap-south-1.on.aws",
            "domainPrefix": "fnurl",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.1",
                "userAgent": "pytest",
            },
            "requestId": "req-1",
            "routeKey": "$default",
            "stage": "$default",
            "time": "24/Oct/2026:10:00:00 +0000",
            "timeEpoch": 1792836000000,
        },
        "body": None if body is None else json.dumps(body),
        "isBase64Encoded": False,
    }
    from tests.conftest import FakeContext

    out = api.handler(event, context or FakeContext())
    raw = out.get("body") or ""
    return out["statusCode"], (json.loads(raw) if raw else None), out.get("headers", {})


NEW = {
    "name": "Nankiv",
    "kind": "personal",
    "checkUrl": "https://nankiv.example/health",
    "note": "Personal site",
}


def create(token: str, **overrides) -> dict:
    status, body, _ = call("POST", "/api/products", body={**NEW, **overrides}, token=token)
    assert status == 201, body
    return body


# --------------------------------------------------------------------------- front door


def test_health_is_public_but_needs_origin_header(env):
    status, body, headers = call("GET", "/api/health")
    assert status == 200
    assert body["status"] == "ok"
    assert headers["cache-control"] == "no-store"
    assert call("GET", "/api/health", origin=None)[0] == 403
    assert call("GET", "/api/health", origin="wrong")[0] == 403


def test_origin_secret_unset_fails_closed(env, monkeypatch):
    monkeypatch.delenv("ORIGIN_VERIFY_SECRET")
    assert call("GET", "/api/health", origin="")[0] == 403


@pytest.mark.parametrize(
    "auth",
    [None, "Basic abc", "Bearer", "Bearer not-a-jwt"],
)
def test_protected_routes_need_a_valid_token(env, auth):
    headers = {"authorization": auth} if auth else {}
    status, body, _ = call("GET", "/api/products", headers=headers)
    assert status == 401
    assert body["error"]["code"] == "unauthorized"


def test_expired_and_forged_tokens_are_rejected(env):
    old = issue_token(JWT_SECRET, utc_now() - timedelta(days=31))[0]
    assert call("GET", "/api/products", token=old)[1]["error"]["message"] == "token expired"
    forged = issue_token("another-secret-another-secret-0123456789", utc_now())[0]
    assert call("GET", "/api/products", token=forged)[0] == 401


def test_unknown_route_is_json_404(env, token):
    status, body, _ = call("GET", "/api/nope", token=token)
    assert status == 404
    assert body["error"]["code"] == "not_found"


# --------------------------------------------------------------------------- login


def test_login_success_returns_a_working_token(env):
    status, body, _ = call("POST", "/api/auth/login", body={"password": PASSWORD})
    assert status == 200
    assert body["expiresAt"] > "2026"
    assert call("GET", "/api/summary", token=body["token"])[0] == 200


def test_login_locks_after_five_failures(env):
    for _ in range(4):
        assert call("POST", "/api/auth/login", body={"password": "nope"})[0] == 401
    status, _, _ = call("POST", "/api/auth/login", body={"password": "nope"})
    assert status == 401
    status, _body, headers = call("POST", "/api/auth/login", body={"password": PASSWORD})
    assert status == 429
    assert int(headers["retry-after"]) > 800


def test_login_success_clears_failures(env):
    call("POST", "/api/auth/login", body={"password": "nope"})
    assert call("POST", "/api/auth/login", body={"password": PASSWORD})[0] == 200
    assert Repo(env.table).get_throttle() == {}


@pytest.mark.parametrize("payload", [{}, {"password": ""}, {"password": "x", "extra": 1}])
def test_login_validation(env, payload):
    assert call("POST", "/api/auth/login", body=payload)[0] == 422


def test_login_requires_configured_secrets(aws, monkeypatch):
    monkeypatch.setenv("ORIGIN_VERIFY_SECRET", ORIGIN)
    status, _body, _ = call("POST", "/api/auth/login", body={"password": PASSWORD})
    assert status == 503


def test_non_json_body_is_400(env):
    event_body = "not json"
    status, _body, _ = call("POST", "/api/auth/login", body=None, headers={})
    assert status == 422  # empty body -> missing password
    # Raw invalid JSON:
    from tests.conftest import FakeContext

    evt = {
        "version": "2.0",
        "rawPath": "/api/auth/login",
        "rawQueryString": "",
        "headers": {"x-beacon-origin": ORIGIN},
        "requestContext": {
            "http": {"method": "POST", "path": "/api/auth/login"},
            "requestId": "r",
            "stage": "$default",
        },
        "body": event_body,
        "isBase64Encoded": False,
    }
    assert api.handler(evt, FakeContext())["statusCode"] == 400


# --------------------------------------------------------------------------- products


def test_create_list_get_update_delete(env, token):
    created = create(token)
    pid = created["id"]
    assert created["status"] == "UNKNOWN"
    assert "evalBase" not in created

    snapshot = env.table.get_item(Key=SNAPSHOT_KEY)["Item"]
    assert [m["id"] for m in snapshot["monitors"]] == [pid]

    status, products, _ = call("GET", "/api/products", token=token)
    assert status == 200
    assert products[0]["id"] == pid
    assert products[0]["strip24h"] == [None] * 24
    assert products[0]["uptime30d"] is None

    status, detail, _ = call("GET", f"/api/products/{pid}", token=token)
    assert status == 200
    assert detail["stats"]["sloTarget"] == 99.5
    assert detail["openIncident"] is None

    status, updated, _ = call(
        "PATCH", f"/api/products/{pid}", body={"name": "Nankiv v2", "intervalMin": 5}, token=token
    )
    assert status == 200
    assert updated["name"] == "Nankiv v2"
    assert env.table.get_item(Key=SNAPSHOT_KEY)["Item"]["monitors"][0]["intervalMin"] == 5

    assert call("DELETE", f"/api/products/{pid}", token=token)[0] == 204
    assert call("GET", f"/api/products/{pid}", token=token)[0] == 404
    assert env.table.get_item(Key=SNAPSHOT_KEY)["Item"]["monitors"] == []


def test_kind_filter_and_sorting(env, token):
    repo = Repo(env.table)
    for pid, name, kind, status in [
        ("A", "Alpha", "personal", "UP"),
        ("B", "Bravo", "client", "DOWN"),
        ("C", "Charlie", "personal", "PAUSED"),
        ("D", "Delta", "client", "DEGRADED"),
    ]:
        repo.create_product(
            Product.model_validate(product_item(id=pid, name=name, kind=kind, status=status))
        )
    _, products, _ = call("GET", "/api/products", token=token)
    assert [p["name"] for p in products] == ["Bravo", "Delta", "Alpha", "Charlie"]
    _, client_only, _ = call("GET", "/api/products", token=token, query={"kind": "client"})
    assert [p["name"] for p in client_only] == ["Bravo", "Delta"]
    _, summary, _ = call("GET", "/api/summary", token=token)
    assert summary["down"] == 1
    assert summary["label"] == "1 product down"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"checkUrl": "http://169.254.169.254/latest/meta-data"}, "url_not_allowed"),
        ({"checkUrl": "https://internal.example/"}, "url_not_allowed"),
        ({"checkUrl": "ftp://nankiv.example/"}, "validation_error"),
        ({"name": ""}, "validation_error"),
        ({"clientName": "ACME"}, "validation_error"),
    ],
)
def test_create_rejects_bad_input(env, token, overrides, code):
    status, body, _ = call("POST", "/api/products", body={**NEW, **overrides}, token=token)
    assert status == 422
    assert body["error"]["code"] == code


def test_unresolvable_host_is_allowed(env, token):
    assert create(token, checkUrl="https://not-yet-live.example/")["checkUrl"].startswith(
        "https://"
    )


def test_patch_rechecks_url_and_rejects_unknown_fields(env, token):
    pid = create(token)["id"]
    status, body, _ = call(
        "PATCH", f"/api/products/{pid}", body={"checkUrl": "http://127.0.0.1:9001/"}, token=token
    )
    assert (status, body["error"]["code"]) == (422, "url_not_allowed")
    assert call("PATCH", f"/api/products/{pid}", body={"bogus": 1}, token=token)[0] == 422


def test_pause_with_open_incident_resolves_and_alerts(env, token):
    repo = Repo(env.table)
    sk = incident_sk("2026-10-24T10:00:00Z", "INC1")
    repo.create_product(Product.model_validate(product_item(status="DOWN", openIncidentSk=sk)))
    env.table.put_item(
        Item={
            "PK": "PRODUCT#01PRODUCT",
            "SK": sk,
            "productId": "01PRODUCT",
            "sk": sk,
            "id": "INC1",
            "state": "OPEN",
            "startedAt": "2026-10-24T10:00:00Z",
            "cause": "HTTP 502",
            "GSI1PK": "INCIDENTS",
            "GSI1SK": "2026-10-24T10:00:00Z#INC1",
            "timeline": [],
        }
    )
    status, body, _ = call("POST", "/api/products/01PRODUCT/pause", token=token)
    assert status == 200
    assert body["status"] == "PAUSED"
    assert body["enabled"] is False
    assert repo.get_incident("01PRODUCT", sk).state == "RESOLVED"
    [alert] = env.alerts()
    assert alert["title"] == "⏸️ PAUSED: Nankiv"
    assert alert["pagerdutyAction"] == "resolve"
    assert env.table.get_item(Key=SNAPSHOT_KEY)["Item"]["monitors"][0]["enabled"] is False

    assert call("POST", "/api/products/01PRODUCT/pause", token=token)[0] == 200  # idempotent
    status, body, _ = call("POST", "/api/products/01PRODUCT/resume", token=token)
    assert (body["status"], body["enabled"]) == ("UNKNOWN", True)
    assert call("POST", "/api/products/01PRODUCT/resume", token=token)[0] == 200


@respx.mock
def test_test_now_runs_a_manual_check(env, token):
    respx.get(f"https://{IP}/health").respond(503)
    pid = create(token)["id"]
    status, body, _ = call("POST", f"/api/products/{pid}/test", token=token)
    assert status == 200
    assert (body["ok"], body["error"]) == (False, "HTTP 503")
    _, checks, _ = call("GET", f"/api/products/{pid}/checks", token=token, query={"limit": "5"})
    assert checks[0]["manual"] is True
    rollups = Repo(env.table).rollups(pid, "R5#", "RH#~")
    assert rollups == {}  # manual checks never count toward uptime


@pytest.mark.parametrize(("rng", "points"), [("24h", 288), ("7d", 168), ("30d", 30)])
def test_series_ranges(env, token, rng, points):
    pid = create(token)["id"]
    status, body, _ = call("GET", f"/api/products/{pid}/series", token=token, query={"range": rng})
    assert status == 200
    assert len(body["points"]) == points


def test_series_rejects_bad_range(env, token):
    pid = create(token)["id"]
    assert call("GET", f"/api/products/{pid}/series", token=token, query={"range": "1y"})[0] == 400
    assert call("GET", f"/api/products/{pid}/checks", token=token, query={"limit": "x"})[0] == 400


def test_detail_stats_from_rollups(env, token):
    repo = Repo(env.table)
    repo.create_product(Product.model_validate(product_item(recentLatencies=list(range(1, 101)))))
    from beacon_core.timeutil import r5_key, rd_key, rh_key

    now = datetime.now(UTC)
    for sk, up, total, down in [
        (r5_key(now), 4, 5, 1),
        (rh_key(now), 59, 60, 1),
        (rd_key(now), 1430, 1440, 10),
    ]:
        env.table.put_item(
            Item={
                "PK": "PRODUCT#01PRODUCT",
                "SK": sk,
                "upMin": up,
                "totalMin": total,
                "downMin": down,
                "latSum": 1000,
                "latCount": 5,
                "latMax": 400,
            }
        )
    _, detail, _ = call("GET", "/api/products/01PRODUCT", token=token)
    stats = detail["stats"]
    assert stats["uptime24h"] == 80.0
    assert stats["uptime7d"] == 98.33
    assert stats["uptime30d"] == 99.3
    assert stats["avgLatency24h"] == 200
    assert stats["p95Latency1h"] == 95
    assert stats["errorBudget"]["budgetMin"] == 7.2
    assert stats["errorBudget"]["remainingMin"] == -2.8


# --------------------------------------------------------------------------- incidents


def _open_incident(env) -> str:
    repo = Repo(env.table)
    sk = incident_sk("2026-10-24T10:00:00Z", "INC1")
    repo.create_product(Product.model_validate(product_item(status="DOWN", openIncidentSk=sk)))
    env.table.put_item(
        Item={
            "PK": "PRODUCT#01PRODUCT",
            "SK": sk,
            "productId": "01PRODUCT",
            "productName": "Nankiv",
            "sk": sk,
            "id": "INC1",
            "state": "OPEN",
            "startedAt": "2026-10-24T10:00:00Z",
            "cause": "HTTP 502",
            "GSI1PK": "INCIDENTS",
            "GSI1SK": "2026-10-24T10:00:00Z#INC1",
            "timeline": [{"at": "2026-10-24T10:00:00Z", "event": "opened"}],
        }
    )
    return sk


@pytest.mark.parametrize("by", ["sk", "ulid"])
def test_acknowledge_incident(env, token, by):
    sk = _open_incident(env)
    ref = quote(sk, safe="") if by == "sk" else "INC1"
    status, body, _ = call("POST", f"/api/products/01PRODUCT/incidents/{ref}/ack", token=token)
    assert status == 200
    assert body["state"] == "ACKNOWLEDGED"
    assert [t["event"] for t in body["timeline"]] == ["opened", "acknowledged"]
    [alert] = env.alerts()
    assert (alert["event"], alert["pagerdutyAction"], alert["dedupKey"]) == (
        "ACKNOWLEDGED",
        "acknowledge",
        "INC1",
    )
    # second ack is a no-op
    assert call("POST", f"/api/products/01PRODUCT/incidents/{ref}/ack", token=token)[0] == 200
    assert len(env.alerts()) == 1

    _, detail, _ = call("GET", "/api/products/01PRODUCT", token=token)
    assert detail["openIncident"]["state"] == "ACKNOWLEDGED"


def test_ack_resolved_incident_conflicts(env, token):
    sk = _open_incident(env)
    Repo(env.table).resolve_incident("01PRODUCT", sk, "2026-10-24T10:05:00Z", 300, "recovered")
    status, _body, _ = call("POST", "/api/products/01PRODUCT/incidents/INC1/ack", token=token)
    assert status == 409


def test_ack_unknown_incident(env, token):
    _open_incident(env)
    assert call("POST", "/api/products/01PRODUCT/incidents/NOPE/ack", token=token)[0] == 404
    bad = quote("INC#broken", safe="")
    assert call("POST", f"/api/products/01PRODUCT/incidents/{bad}/ack", token=token)[0] == 400


def test_incident_feeds(env, token):
    sk = _open_incident(env)
    _, open_feed, _ = call("GET", "/api/incidents", token=token, query={"state": "open"})
    assert [i["id"] for i in open_feed] == ["INC1"]
    Repo(env.table).resolve_incident("01PRODUCT", sk, "2026-10-24T10:05:00Z", 300, "recovered")
    assert call("GET", "/api/incidents", token=token, query={"state": "open"})[1] == []
    assert len(call("GET", "/api/incidents", token=token)[1]) == 1
    assert len(call("GET", "/api/products/01PRODUCT/incidents", token=token)[1]) == 1
    assert call("GET", "/api/incidents", token=token, query={"state": "closed"})[0] == 400


def test_delete_product_with_open_incident_resolves_it(env, token):
    sk = _open_incident(env)
    assert call("DELETE", "/api/products/01PRODUCT", token=token)[0] == 204
    assert Repo(env.table).get_incident("01PRODUCT", sk).state == "RESOLVED"


# ------------------------------------------------- push, notifications, demo, settings

SUB = {
    "endpoint": "https://web.push.apple.com/QGx",
    "keys": {"p256dh": "BNc", "auth": "tBH"},
    "expirationTime": None,
}


def test_push_subscription_lifecycle(env, token):
    assert call("POST", "/api/push/subscriptions", body=SUB, token=token)[0] == 201
    assert call("POST", "/api/push/subscriptions", body=SUB, token=token)[0] == 201  # upsert
    _, settings, _ = call("GET", "/api/settings", token=token)
    assert settings["channels"]["pushDevices"] == 1
    assert (
        call("DELETE", "/api/push/subscriptions", body={"endpoint": SUB["endpoint"]}, token=token)[
            0
        ]
        == 204
    )
    assert call("GET", "/api/settings", token=token)[1]["channels"]["pushDevices"] == 0
    assert call("DELETE", "/api/push/subscriptions", body={}, token=token)[0] == 400


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://web.push.apple.com/x",
        "https://169.254.169.254/x",
        "https://evil.example/push",
        "https://apple.com.evil.example/",
    ],
)
def test_push_endpoint_allowlist(env, token, endpoint):
    status, body, _ = call(
        "POST", "/api/push/subscriptions", body={**SUB, "endpoint": endpoint}, token=token
    )
    assert (status, body["error"]["code"]) == (422, "endpoint_not_allowed")


def test_test_notification_goes_through_sns(env, token):
    assert call("POST", "/api/notifications/test", token=token)[0] == 202
    [alert] = env.alerts()
    assert alert["event"] == "TEST"
    assert env.published[0]["MessageAttributes"]["event"]["StringValue"] == "TEST"


def test_demo_break_and_fix(env, token):
    assert call("POST", "/api/demo/break", token=token)[1] == {"healthy": False}
    assert env.ssm.get_parameter(Name="/beacon/demo/healthy")["Parameter"]["Value"] == "false"
    assert call("GET", "/api/settings", token=token)[1]["demo"] == "broken"
    assert call("POST", "/api/demo/fix", token=token)[1] == {"healthy": True}
    assert call("GET", "/api/settings", token=token)[1]["demo"] == "healthy"


def test_settings_get_and_patch(env, token):
    _, body, _ = call("GET", "/api/settings", token=token)
    assert body["settings"] == {
        "quorum": None,
        "pushEnabled": True,
        "emailEnabled": True,
        "pagerdutyEnabled": True,
    }
    assert body["channels"]["email"] is True
    assert body["channels"]["pagerduty"] is False
    status, patched, _ = call(
        "PATCH", "/api/settings", body={"quorum": 2, "pagerdutyEnabled": False}, token=token
    )
    assert status == 200
    assert patched["quorum"] == 2
    assert patched["pushEnabled"] is True
    assert call("PATCH", "/api/settings", body={"quorum": 9}, token=token)[0] == 422
    assert call("PATCH", "/api/settings", body={"smsEnabled": True}, token=token)[0] == 422


def test_email_toggle_sets_the_sns_email_attribute(env, token):
    call("POST", "/api/notifications/test", token=token)
    call("PATCH", "/api/settings", body={"emailEnabled": False}, token=token)
    call("POST", "/api/notifications/test", token=token)
    flags = [p["MessageAttributes"]["email"]["StringValue"] for p in env.published]
    assert flags == ["on", "off"]
