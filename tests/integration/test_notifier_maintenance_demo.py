"""Notifier (Web Push + PagerDuty), maintenance (TLS + daily summary) and the demo target."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import respx
from pywebpush import WebPushException

from beacon_core.alerts import down_alert, make_test_alert, recovered_alert
from beacon_core.models import Alert, Product, Settings
from beacon_core.repo_dynamo import Repo
from beacon_core.state_machine import IncidentOpened, IncidentResolved, incident_sk
from demo_target import app as demo
from maintenance import app as maintenance
from notifier import app as notifier
from tests.conftest import product_item

PD_URL = "https://events.pagerduty.com/v2/enqueue"


def sns_event(alert: Alert) -> dict:
    return {"Records": [{"Sns": {"MessageId": "sns-1", "Message": alert.model_dump_json()}}]}


@pytest.fixture
def product() -> Product:
    return Product.model_validate(product_item())


@pytest.fixture
def opened() -> IncidentOpened:
    return IncidentOpened(
        sk=incident_sk("2026-10-24T10:00:00Z", "INC1"),
        id="INC1",
        started_at="2026-10-24T10:00:00Z",
        cause="HTTP 502",
        first_error="HTTP 502",
        failing_regions=("ap-south-1",),
    )


@pytest.fixture
def push_env(aws, monkeypatch):
    aws.set_param("/beacon/vapid_private_key", "private-key")
    aws.set_param("/beacon/vapid_subject", "mailto:owner@example.com")
    repo = Repo(aws.table)
    for name in ("a", "b"):
        repo.put_subscription(
            name,
            {
                "endpoint": f"https://web.push.apple.com/{name}",
                "keys": {"p256dh": "k", "auth": "a"},
            },
        )
    sent: list[dict] = []
    monkeypatch.setattr(notifier, "webpush", lambda **kw: sent.append(kw))
    return SimpleNamespace(repo=repo, sent=sent)


@respx.mock
def test_down_alert_pushes_and_pages(aws, push_env, product, opened, lambda_context):
    aws.set_param("/beacon/pagerduty_routing_key", "R0UTING")
    pd = respx.post(PD_URL).respond(202, json={"status": "success"})
    out = notifier.handler(sns_event(down_alert(product, opened)), lambda_context)

    assert out["delivered"][0] == {
        "event": "DOWN",
        "pushSent": 2,
        "pushFailed": 0,
        "pagerduty": True,
    }
    payload = json.loads(push_env.sent[0]["data"])
    assert payload == {
        "title": "🔴 DOWN: Nankiv",
        "body": "HTTP 502 (ap-south-1)",
        "url": "/p/01PRODUCT",
        "tag": "01PRODUCT",
    }
    assert push_env.sent[0]["headers"] == {"Urgency": "high"}
    assert push_env.sent[0]["vapid_claims"] == {"sub": "mailto:owner@example.com"}
    body = json.loads(pd.calls.last.request.content)
    assert body["event_action"] == "trigger"
    assert body["dedup_key"] == "INC1"
    assert body["payload"]["severity"] == "critical"
    assert body["links"][0]["href"] == "https://beacon.example.cloudfront.net/p/01PRODUCT"


@respx.mock
def test_recovered_sends_pagerduty_resolve(aws, push_env, product, lambda_context):
    aws.set_param("/beacon/pagerduty_routing_key", "R0UTING")
    pd = respx.post(PD_URL).respond(202)
    resolved = IncidentResolved(
        sk=incident_sk("2026-10-24T10:00:00Z", "INC1"),
        resolved_at="2026-10-24T10:06:12Z",
        duration_sec=372,
    )
    notifier.handler(sns_event(recovered_alert(product, resolved)), lambda_context)
    body = json.loads(pd.calls.last.request.content)
    assert body == {"routing_key": "R0UTING", "event_action": "resolve", "dedup_key": "INC1"}
    assert json.loads(push_env.sent[0]["data"])["body"] == "down for 6m 12s"


def test_gone_subscriptions_are_deleted(aws, push_env, monkeypatch, lambda_context):
    def gone(**kw):
        if kw["subscription_info"]["endpoint"].endswith("/a"):
            raise WebPushException("gone", response=SimpleNamespace(status_code=410))

    monkeypatch.setattr(notifier, "webpush", gone)
    out = notifier.handler(sns_event(make_test_alert()), lambda_context)
    assert out["delivered"][0]["pushSent"] == 1
    assert [s["SK"] for s in push_env.repo.list_subscriptions()] == ["b"]


def test_all_push_failures_raise_for_retry(aws, push_env, monkeypatch, lambda_context):
    def fail(**kw):
        raise WebPushException("boom", response=SimpleNamespace(status_code=500))

    monkeypatch.setattr(notifier, "webpush", fail)
    with pytest.raises(notifier.DeliveryError):
        notifier.handler(sns_event(make_test_alert()), lambda_context)


@respx.mock
def test_pagerduty_failure_raises(aws, push_env, product, opened, lambda_context):
    aws.set_param("/beacon/pagerduty_routing_key", "R0UTING")
    respx.post(PD_URL).respond(500)
    with pytest.raises(notifier.DeliveryError, match="HTTP 500"):
        notifier.handler(sns_event(down_alert(product, opened)), lambda_context)


def test_unconfigured_channels_are_skipped(aws, product, opened, lambda_context):
    out = notifier.handler(sns_event(down_alert(product, opened)), lambda_context)
    assert out["delivered"][0] == {
        "event": "DOWN",
        "pushSent": 0,
        "pushFailed": 0,
        "pagerduty": False,
    }


def test_disabled_push_channel(aws, push_env, lambda_context):
    push_env.repo.put_settings(Settings(push_enabled=False))
    notifier.handler(sns_event(make_test_alert()), lambda_context)
    assert push_env.sent == []


# --------------------------------------------------------------------------- maintenance


def test_maintenance_tls_alerts_once_per_threshold(aws, monkeypatch, lambda_context):
    repo = Repo(aws.table)
    repo.create_product(Product.model_validate(product_item(id="TLS", name="Sorry No Proxy")))
    repo.create_product(
        Product.model_validate(product_item(id="HTTP", checkUrl="http://plain.example/"))
    )
    now = datetime.now(UTC)
    expiry = {"value": now + timedelta(days=9, hours=1)}

    async def fake_expiry(url, **kw):
        assert url.startswith("https://")
        return expiry["value"]

    monkeypatch.setattr(maintenance, "fetch_cert_expiry", fake_expiry)
    out = maintenance.handler({}, lambda_context)
    assert out["tlsAlerts"] == 1
    tls = [a for a in aws.alerts() if a["event"] == "TLS_EXPIRING"]
    assert tls[0]["title"] == "🔐 TLS expiring: Sorry No Proxy"
    assert tls[0]["body"] == "9 days left"
    assert repo.get_product("TLS").cert_expires_at is not None

    assert maintenance.handler({}, lambda_context)["tlsAlerts"] == 0  # same level: no repeat
    expiry["value"] = now + timedelta(days=6, hours=1)
    assert maintenance.handler({}, lambda_context)["tlsAlerts"] == 1  # crossed 7 days


def test_maintenance_tls_failure_is_tolerated(aws, monkeypatch, lambda_context):
    Repo(aws.table).create_product(Product.model_validate(product_item()))

    async def broken(url, **kw):
        raise OSError("connection reset")

    monkeypatch.setattr(maintenance, "fetch_cert_expiry", broken)
    assert maintenance.handler({}, lambda_context)["tlsAlerts"] == 0


def test_daily_summary(aws, monkeypatch, lambda_context):
    repo = Repo(aws.table)
    repo.create_product(Product.model_validate(product_item(checkUrl="http://a.example/")))
    from beacon_core.timeutil import IST, rd_key

    yesterday = datetime.now(UTC).astimezone(IST) - timedelta(days=1)
    aws.table.put_item(
        Item={
            "PK": "PRODUCT#01PRODUCT",
            "SK": rd_key(yesterday),
            "upMin": 1439,
            "totalMin": 1440,
            "downMin": 1,
        }
    )
    out = maintenance.handler({}, lambda_context)
    assert out["summary"] == {"products": 1, "uptime": 99.93, "incidents": 0}
    [summary] = [a for a in aws.alerts() if a["event"] == "DAILY_SUMMARY"]
    assert summary["body"] == "1 products · 99.93% up yesterday · 0 incidents"


# --------------------------------------------------------------------------- demo target


@pytest.mark.parametrize(
    ("value", "status"), [("true", 200), ("false", 503), ("FALSE", 503), ("unset", 200)]
)
def test_demo_target(aws, value, status, lambda_context):
    aws.ssm.put_parameter(Name="/beacon/demo/healthy", Value=value, Type="String", Overwrite=True)
    from beacon_core import aws as beacon_aws

    beacon_aws._params.clear()
    out = demo.handler({"rawPath": "/"}, lambda_context)
    assert out["statusCode"] == status
    assert out["headers"]["cache-control"] == "no-store"
