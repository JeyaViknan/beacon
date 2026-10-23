"""Probe handler end to end: snapshot in DynamoDB (moto) -> checks (respx) -> one SQS message."""

import json
from datetime import UTC, datetime

import pytest
import respx

from beacon_core.models import MonitorSpec, Product
from beacon_core.snapshot import SNAPSHOT_KEY, SnapshotCache, build_snapshot, due_monitors
from probe import app as probe

IP = "93.184.216.34"


async def fake_resolver(host: str, port: int) -> list[str]:
    return [IP]


@pytest.fixture(autouse=True)
def _fresh_probe(monkeypatch):
    probe._table.cache_clear()
    probe._sqs.cache_clear()
    monkeypatch.setattr(probe, "RESOLVER", fake_resolver)
    monkeypatch.setattr(probe, "snapshot_cache", SnapshotCache(probe._load_snapshot))


def put_snapshot(table, monitors: list[dict]) -> None:
    table.put_item(
        Item={
            **SNAPSHOT_KEY,
            "version": 3,
            "updatedAt": "2026-10-24T10:00:00Z",
            "monitors": monitors,
        }
    )


def receive(aws) -> list[dict]:
    resp = aws.sqs.receive_message(QueueUrl=aws.queue_url, MaxNumberOfMessages=10)
    return [json.loads(m["Body"]) for m in resp.get("Messages", [])]


@respx.mock
def test_probe_checks_due_monitors_and_sends_one_message(aws, lambda_context):
    respx.get(f"https://{IP}/up").respond(200)
    respx.get(f"https://{IP}/down").respond(502)
    put_snapshot(
        aws.table,
        [
            {
                "id": "UP1",
                "checkUrl": "https://up.example/up",
                "intervalMin": 1,
                "enabled": True,
                "timeoutMs": 10000,
            },
            {
                "id": "DN1",
                "checkUrl": "https://down.example/down",
                "intervalMin": 1,
                "enabled": True,
            },
            {"id": "OFF", "checkUrl": "https://off.example/", "intervalMin": 1, "enabled": False},
            {"id": "FIVE", "checkUrl": "https://five.example/", "intervalMin": 5, "enabled": True},
        ],
    )
    out = probe.handler({"scheduledTime": "2026-10-24T10:16:00Z"}, lambda_context)
    assert out["checked"] == 2
    assert out["failed"] == 1
    assert out["snapshotVersion"] == 3

    [message] = receive(aws)
    assert message["region"] == "ap-south-1"
    assert message["runAt"] == "2026-10-24T10:16:00Z"
    by_id = {r["productId"]: r for r in message["results"]}
    assert set(by_id) == {"UP1", "DN1"}
    assert by_id["UP1"]["ok"] is True
    assert by_id["DN1"] == {
        "productId": "DN1",
        "ok": False,
        "httpCode": 502,
        "latencyMs": by_id["DN1"]["latencyMs"],
        "error": "HTTP 502",
        "keywordOk": None,
    }


def test_probe_sends_heartbeat_message_with_no_snapshot(aws, lambda_context):
    out = probe.handler({}, lambda_context)
    assert out["checked"] == 0
    [message] = receive(aws)
    assert message["results"] == []


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ({"scheduledTime": "2026-10-24T10:16:42Z"}, datetime(2026, 10, 24, 10, 16, tzinfo=UTC)),
        ({"scheduledTime": "not-a-date"}, None),
        ({}, None),
        ("raw", None),
    ],
)
def test_run_time(event, expected):
    got = probe.run_time(event)
    assert got.second == 0
    if expected is not None:
        assert got == expected


def test_snapshot_cache_respects_ttl():
    loads = []
    now = [0.0]

    def load():
        loads.append(1)
        return {"version": len(loads), "updatedAt": "2026-10-24T10:00:00Z", "monitors": []}

    cache = SnapshotCache(load, ttl=30, clock=lambda: now[0])
    assert cache.get().version == 1
    now[0] = 29.9
    assert cache.get().version == 1
    now[0] = 30.0
    assert cache.get().version == 2


def test_build_snapshot_and_due_monitors():
    products = [
        Product.model_validate(
            {
                "id": pid,
                "name": pid,
                "kind": "personal",
                "checkUrl": f"https://{pid}.example/",
                "intervalMin": interval,
                "enabled": enabled,
                "createdAt": "2026-10-01T00:00:00Z",
                "updatedAt": "2026-10-01T00:00:00Z",
            }
        )
        for pid, interval, enabled in [("b", 1, True), ("a", 5, True), ("c", 1, False)]
    ]
    snap = build_snapshot(products, version=7, now=datetime(2026, 10, 24, tzinfo=UTC))
    assert [m.id for m in snap.monitors] == ["a", "b", "c"]
    assert isinstance(snap.monitors[0], MonitorSpec)
    at_5 = datetime(2026, 10, 24, 10, 15, tzinfo=UTC)
    at_6 = datetime(2026, 10, 24, 10, 16, tzinfo=UTC)
    assert [m.id for m in due_monitors(snap, at_5)] == ["a", "b"]
    assert [m.id for m in due_monitors(snap, at_6)] == ["b"]
