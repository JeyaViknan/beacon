import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from beacon_core import tls
from beacon_core.alerts import daily_summary_alert, email_subject, make_test_alert, tls_alert
from beacon_core.auth import (
    AuthError,
    Throttle,
    bearer_token,
    hash_password,
    issue_token,
    same_secret,
    verify_password,
    verify_token,
)
from beacon_core.ddb import Update, from_ddb, to_ddb
from beacon_core.models import Alert, AlertEvent, Product, Severity

NOW = datetime(2026, 10, 24, 10, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- TLS


class FakeWriter:
    def __init__(self, cert):
        self.cert = cert
        self.closed = False

    def get_extra_info(self, name):
        assert name == "peercert"
        return self.cert

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


async def resolver(host, port):
    return ["93.184.216.34"]


def test_fetch_cert_expiry_connects_to_pinned_ip_with_sni(monkeypatch):
    seen = {}
    writer = FakeWriter({"notAfter": "Nov  2 12:00:00 2026 GMT"})

    async def fake_open(host, port, *, ssl, server_hostname):
        seen.update(host=host, port=port, sni=server_hostname)
        return None, writer

    monkeypatch.setattr(tls.asyncio, "open_connection", fake_open)
    expires = asyncio.run(tls.fetch_cert_expiry("https://example.com:8443/x", resolver=resolver))
    assert expires == datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    assert seen == {"host": "93.184.216.34", "port": 8443, "sni": "example.com"}
    assert writer.closed


def test_fetch_cert_expiry_rejects_http_and_missing_cert(monkeypatch):
    with pytest.raises(ValueError, match="https"):
        asyncio.run(tls.fetch_cert_expiry("http://example.com/", resolver=resolver))

    async def fake_open(host, port, *, ssl, server_hostname):
        return None, FakeWriter({})

    monkeypatch.setattr(tls.asyncio, "open_connection", fake_open)
    with pytest.raises(ValueError, match="notAfter"):
        asyncio.run(tls.fetch_cert_expiry("https://example.com/", resolver=resolver))


@pytest.mark.parametrize(
    ("days", "already", "expected"),
    [
        (30, None, (False, None)),
        (30, 7, (False, None)),  # renewed: reset
        (14, None, (True, 14)),
        (10, 14, (False, 14)),
        (7, 14, (True, 7)),
        (3, 7, (False, 7)),
        (5, None, (True, 7)),
        (-1, None, (True, 7)),
    ],
)
def test_tls_alert_levels(days, already, expected):
    assert tls.tls_alert_level(days, already) == expected


def test_days_left_floors():
    assert tls.days_left(NOW + timedelta(days=9, hours=23), NOW) == 9
    assert tls.days_left(NOW - timedelta(hours=1), NOW) == -1


# --------------------------------------------------------------------------- auth


def test_password_hash_roundtrip():
    stored = hash_password("s3cret")
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, "s3cret") is True
    assert verify_password(stored, "wrong") is False
    assert verify_password("not-a-hash", "s3cret") is False


def test_token_roundtrip_and_failures():
    token, expires = issue_token("k" * 32, NOW)
    assert expires == "2026-11-23T10:00:00Z"
    assert verify_token("k" * 32, token, NOW)["sub"] == "admin"
    with pytest.raises(AuthError, match="expired"):
        verify_token("k" * 32, token, NOW + timedelta(days=31))
    with pytest.raises(AuthError):
        verify_token("other" * 8, token, NOW)


def test_token_with_alg_none_is_rejected():
    import jwt

    unsigned = jwt.encode(
        {"sub": "admin", "iss": "beacon", "iat": 1, "exp": 9_999_999_999}, None, algorithm="none"
    )
    with pytest.raises(AuthError):
        verify_token("k" * 32, unsigned, NOW)


def test_token_with_wrong_subject_is_rejected():
    import jwt

    claims = {
        "sub": "intruder",
        "iss": "beacon",
        "iat": int(NOW.timestamp()),
        "exp": int(NOW.timestamp()) + 60,
    }
    with pytest.raises(AuthError, match="subject"):
        verify_token("k" * 32, jwt.encode(claims, "k" * 32, algorithm="HS256"), NOW)


@pytest.mark.parametrize(
    ("header", "ok"),
    [
        ("Bearer abc", True),
        ("bearer abc", True),
        (None, False),
        ("", False),
        ("Basic abc", False),
        ("Bearer ", False),
    ],
)
def test_bearer_token(header, ok):
    if ok:
        assert bearer_token(header) == "abc"
    else:
        with pytest.raises(AuthError):
            bearer_token(header)


def test_same_secret():
    assert same_secret("abc", "abc") is True
    assert same_secret("abc", "abd") is False
    assert same_secret("abc", None) is False
    assert same_secret("", "") is False


def test_throttle_locks_after_five_and_resets_after_expiry():
    t = Throttle()
    for _ in range(4):
        t = t.after_failure(NOW)
        assert t.retry_after(NOW) == 0
    t = t.after_failure(NOW)
    assert t.retry_after(NOW) == 900
    later = NOW + timedelta(minutes=16)
    assert t.retry_after(later) == 0
    assert t.after_failure(later) == Throttle(failures=1)
    assert Throttle.from_item({"failures": 2}) == Throttle(failures=2)


# --------------------------------------------------------------------------- alerts + ddb helpers


def test_email_subject_is_ascii_and_short():
    alert = Alert(
        event=AlertEvent.DOWN,
        severity=Severity.CRITICAL,
        title="🔴 DOWN: Café Ünïcode",
        body="x" * 200,
    )
    subject = email_subject(alert)
    assert subject.isascii()
    assert len(subject) < 100
    assert subject.startswith("[Beacon] DOWN: Caf")


def test_alert_texts():
    product = Product.model_validate(
        {
            "id": "P",
            "name": "Sorry No Proxy",
            "kind": "client",
            "checkUrl": "https://x.example/",
            "createdAt": "2026-10-01T00:00:00Z",
            "updatedAt": "2026-10-01T00:00:00Z",
        }
    )
    assert tls_alert(product, 1).body == "1 day left"
    assert (
        daily_summary_alert(12, 99.98, 0).body == "12 products · 99.98% up yesterday · 0 incidents"
    )
    assert daily_summary_alert(1, None, 1).body == "1 products · no data · 1 incident"
    assert make_test_alert().severity is Severity.INFO


def test_ddb_conversions_and_update_builder():
    assert to_ddb({"a": 1.5, "b": [0.1], "c": True, "d": None}) == {
        "a": __import__("decimal").Decimal("1.5"),
        "b": [__import__("decimal").Decimal("0.1")],
        "c": True,
        "d": None,
    }
    from decimal import Decimal

    assert from_ddb({"x": Decimal("2"), "y": [Decimal("2.5")]}) == {"x": 2, "y": [2.5]}
    upd = Update().set("a", 1).set("b", None).add("c", 2)
    assert upd.expression == "SET #n0 = :v0 REMOVE #n1 ADD #n2 :v1"
    assert "ExpressionAttributeValues" in upd.kwargs("x")
    only_remove = Update().set("gone", None)
    assert "ExpressionAttributeValues" not in only_remove.kwargs()
