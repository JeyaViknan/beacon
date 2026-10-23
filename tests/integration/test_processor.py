"""Processor end to end on SQS batches against moto DynamoDB/SNS/SSM."""

import json
from decimal import Decimal

import pytest
import respx

from beacon_core.models import Product
from beacon_core.repo_dynamo import ConflictError, Repo
from processor import app as processor
from tests.conftest import product_item

PID = "01PRODUCT"


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    processor._settings_cache.clear()


@pytest.fixture
def repo(aws) -> Repo:
    r = Repo(aws.table)
    r.create_product(Product.model_validate(product_item(openAfter=2, resolveAfter=2)))
    return r


def sqs_event(*messages: dict, ids: list[str] | None = None) -> dict:
    return {
        "Records": [
            {
                "messageId": (ids or [f"m{i}" for i in range(len(messages))])[i],
                "receiptHandle": "rh",
                "body": json.dumps(m),
                "attributes": {"ApproximateReceiveCount": "1"},
                "messageAttributes": {},
                "md5OfBody": "",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:ap-south-1:123456789012:beacon-results",
                "awsRegion": "ap-south-1",
            }
            for i, m in enumerate(messages)
        ]
    }


def message(minute: int, ok: bool, *, latency: int = 120, region: str = "ap-south-1") -> dict:
    return {
        "region": region,
        "runAt": f"2026-10-24T10:{minute:02d}:00Z",
        "results": [
            {
                "productId": PID,
                "ok": ok,
                "httpCode": 200 if ok else 502,
                "latencyMs": latency,
                "error": None if ok else "HTTP 502",
                "keywordOk": None,
            }
        ],
    }


def rollup(aws, sk: str) -> dict:
    return aws.table.get_item(Key={"PK": f"PRODUCT#{PID}", "SK": sk}).get("Item", {})


def test_outage_opens_and_resolves_incident_with_alerts(aws, repo, lambda_context):
    for minute, ok in enumerate([True, False, False, True, True]):
        out = processor.handler(sqs_event(message(minute, ok)), lambda_context)
        assert out == {"batchItemFailures": []}

    product = repo.get_product(PID)
    assert product.status == "UP"
    assert product.open_incident_sk is None
    [incident] = repo.incidents_for(PID)
    assert incident.state == "RESOLVED"
    assert incident.started_at == "2026-10-24T10:01:00Z"
    assert incident.resolved_at == "2026-10-24T10:03:00Z"
    assert incident.duration_sec == 120
    assert [t.event for t in incident.timeline] == ["opened", "resolved"]

    alerts = aws.alerts()
    assert [a["event"] for a in alerts] == ["DOWN", "RECOVERED"]
    assert alerts[0]["title"] == "🔴 DOWN: Nankiv"
    assert alerts[0]["body"] == "HTTP 502 (ap-south-1)"
    assert alerts[0]["pagerdutyAction"] == "trigger"
    assert alerts[1]["body"] == "down for 2m 0s"
    assert alerts[1]["dedupKey"] == alerts[0]["dedupKey"] == incident.id

    first = aws.published[0]
    assert first["MessageAttributes"]["severity"]["StringValue"] == "critical"
    assert first["Subject"] == "[Beacon] DOWN: Nankiv - HTTP 502 (ap-south-1)"
    email = json.loads(first["Message"])["email"]
    assert "Open in Beacon: https://beacon.example.cloudfront.net/p/01PRODUCT" in email


def test_redelivered_message_is_applied_once(aws, repo, lambda_context):
    event = sqs_event(message(0, False), message(1, False))
    processor.handler(event, lambda_context)
    processor.handler(event, lambda_context)  # SQS at-least-once: the same batch again

    product = repo.get_product(PID)
    assert product.consecutive_failures == 2
    assert len(repo.incidents_for(PID)) == 1
    assert [a["event"] for a in aws.alerts()] == ["DOWN"]
    hour = rollup(aws, "RH#2026102410")
    assert hour["totalMin"] == Decimal(2)
    assert hour["downMin"] == Decimal(2)
    assert len(repo.recent_checks(PID)) == 2


def test_redelivery_after_other_region_moved_on_is_still_a_duplicate(aws, repo, lambda_context):
    processor.handler(sqs_event(message(0, True)), lambda_context)
    processor.handler(sqs_event(message(1, True)), lambda_context)
    # Region state now says 10:01; a replay of 10:00 is caught by the state machine itself.
    processor.handler(sqs_event(message(0, True)), lambda_context)
    assert rollup(aws, "RD#20261024")["totalMin"] == Decimal(2)


def test_rollups_and_latency_max(aws, repo, lambda_context):
    processor.handler(sqs_event(message(0, True, latency=100)), lambda_context)
    processor.handler(sqs_event(message(1, True, latency=300)), lambda_context)
    processor.handler(sqs_event(message(2, True, latency=200)), lambda_context)
    r5 = rollup(aws, "R5#202610241000")
    assert r5["upMin"] == Decimal(3)
    assert r5["totalMin"] == Decimal(3)
    assert r5["latSum"] == Decimal(600)
    assert r5["latCount"] == Decimal(3)
    assert r5["latMax"] == Decimal(300)
    assert "ttl" in r5


def test_degraded_alert(aws, repo, lambda_context):
    for minute in range(3):
        processor.handler(sqs_event(message(minute, True, latency=3_400)), lambda_context)
    assert repo.get_product(PID).status == "DEGRADED"
    [alert] = aws.alerts()
    assert alert["title"] == "🟠 SLOW: Nankiv"
    assert alert["body"] == "3.4 s avg (limit 2 s)"
    assert alert["severity"] == "warning"
    assert alert["pagerdutyAction"] is None


def test_unknown_and_paused_products_are_skipped(aws, repo, lambda_context):
    msg = message(0, False)
    msg["results"][0]["productId"] = "GONE"
    assert processor.handler(sqs_event(msg), lambda_context) == {"batchItemFailures": []}

    repo.create_product(Product.model_validate(product_item(id="PAUSED", enabled=False)))
    msg["results"][0]["productId"] = "PAUSED"
    processor.handler(sqs_event(msg), lambda_context)
    assert repo.recent_checks("PAUSED") == []


def test_poison_message_is_reported_as_batch_item_failure(aws, repo, lambda_context, monkeypatch):
    pings = []
    monkeypatch.setattr(processor, "ping_healthchecks", lambda: pings.append(1))
    event = sqs_event(message(0, True), {"not": "a probe message"}, ids=["good", "bad"])
    out = processor.handler(event, lambda_context)
    assert out == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert pings == []  # no heartbeat while something is failing
    assert repo.get_product(PID).status == "UP"


@respx.mock
def test_healthchecks_ping_after_clean_batch(aws, repo, lambda_context):
    route = respx.get("https://hc-ping.com/abc").respond(200)
    aws.set_param("/beacon/healthchecks_ping_url", "https://hc-ping.com/abc")
    processor.handler(sqs_event(message(0, True)), lambda_context)
    assert route.call_count == 1


def test_empty_heartbeat_message_still_pings(aws, repo, lambda_context, monkeypatch):
    pings = []
    monkeypatch.setattr(processor, "ping_healthchecks", lambda: pings.append(1))
    empty = {"region": "ap-south-1", "runAt": "2026-10-24T10:00:00Z", "results": []}
    processor.handler(sqs_event(empty), lambda_context)
    assert pings == [1]


def test_version_conflict_is_retried(aws, repo, monkeypatch):
    real = repo.apply_evaluation
    calls = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ConflictError(PID)
        return real(*args, **kwargs)

    from beacon_core import aws as beacon_aws

    monkeypatch.setattr(beacon_aws.repo(), "apply_evaluation", flaky)
    msg = message(0, True)
    processor.process_result(
        msg["region"], msg["runAt"], processor.CheckResult.model_validate(msg["results"][0])
    )
    assert len(calls) == 2


def test_gives_up_after_repeated_conflicts(aws, repo, monkeypatch):
    from beacon_core import aws as beacon_aws

    def always(*args, **kwargs):
        raise ConflictError(PID)

    monkeypatch.setattr(beacon_aws.repo(), "apply_evaluation", always)
    msg = message(0, True)
    with pytest.raises(ConflictError):
        processor.process_result(
            msg["region"], msg["runAt"], processor.CheckResult.model_validate(msg["results"][0])
        )


def test_alert_publish_failure_does_not_fail_the_batch(aws, repo, lambda_context, monkeypatch):
    from botocore.exceptions import ClientError

    from beacon_core import aws as beacon_aws

    def boom(**kwargs):
        raise ClientError({"Error": {"Code": "InternalError", "Message": "x"}}, "Publish")

    monkeypatch.setattr(beacon_aws.sns(), "publish", boom)
    processor.handler(sqs_event(message(0, False)), lambda_context)
    out = processor.handler(sqs_event(message(1, False)), lambda_context)
    assert out == {"batchItemFailures": []}
    assert repo.get_product(PID).status == "DOWN"
