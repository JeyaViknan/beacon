from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from beacon_core.models import Product, ProductInput, parse_status_ranges, status_matches
from beacon_core.timeutil import (
    epoch_minute,
    format_duration,
    format_ist,
    parse_iso,
    r5_key,
    rd_key,
    rh_key,
    to_iso,
    ttl_after,
)

# --- timeutil -------------------------------------------------------------------------------


def test_to_iso_and_parse_roundtrip():
    dt = datetime(2026, 10, 24, 10, 15, 7, 999, tzinfo=UTC)
    assert to_iso(dt) == "2026-10-24T10:15:07Z"
    assert parse_iso("2026-10-24T10:15:07Z") == dt.replace(microsecond=0)
    assert parse_iso("2026-10-24T15:45:07+05:30") == dt.replace(microsecond=0)


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError, match="naive"):
        to_iso(datetime(2026, 1, 1))  # noqa: DTZ001
    with pytest.raises(ValueError, match="without timezone"):
        parse_iso("2026-10-24T10:15:07")


@pytest.mark.parametrize(
    ("dt", "r5", "rh", "rd"),
    [
        (
            datetime(2026, 10, 24, 10, 17, 59, tzinfo=UTC),
            "R5#202610241015",
            "RH#2026102410",
            "RD#20261024",
        ),
        (
            datetime(2026, 10, 24, 10, 0, tzinfo=UTC),
            "R5#202610241000",
            "RH#2026102410",
            "RD#20261024",
        ),
        # 18:30 UTC is midnight IST: the daily bucket rolls over to the next IST date.
        (
            datetime(2026, 10, 24, 18, 29, tzinfo=UTC),
            "R5#202610241825",
            "RH#2026102418",
            "RD#20261024",
        ),
        (
            datetime(2026, 10, 24, 18, 30, tzinfo=UTC),
            "R5#202610241830",
            "RH#2026102418",
            "RD#20261025",
        ),
    ],
)
def test_bucket_keys(dt, r5, rh, rd):
    assert (r5_key(dt), rh_key(dt), rd_key(dt)) == (r5, rh, rd)


def test_epoch_minute_and_ttl():
    dt = datetime(2026, 10, 24, 10, 15, 59, tzinfo=UTC)
    assert epoch_minute(dt) == epoch_minute(dt.replace(second=0))
    assert epoch_minute(dt + timedelta(seconds=1)) == epoch_minute(dt) + 1
    assert ttl_after(dt, hours=48) - int(dt.timestamp()) == 48 * 3600


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0s"), (45, "45s"), (372, "6m 12s"), (8_040, "2h 14m"), (273_600, "3d 4h"), (-5, "0s")],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_format_ist():
    assert format_ist(datetime(2026, 10, 24, 10, 15, tzinfo=UTC)) == "24 Oct 15:45 IST"
    other = timezone(timedelta(hours=-5))
    assert format_ist(datetime(2026, 10, 24, 5, 15, tzinfo=other)) == "24 Oct 15:45 IST"


# --- models ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "code", "expected"),
    [
        ("200-399", 200, True),
        ("200-399", 399, True),
        ("200-399", 404, False),
        ("200", 200, True),
        ("200", 201, False),
        ("200,204,301-302", 302, True),
        ("200, 204", 204, True),
    ],
)
def test_status_matches(spec, code, expected):
    assert status_matches(code, spec) is expected


@pytest.mark.parametrize("spec", ["", "abc", "200-", "99", "600", "399-200", "200-399,x"])
def test_invalid_status_specs(spec):
    with pytest.raises(ValueError):
        parse_status_ranges(spec)


VALID = {"name": "  Nankiv ", "kind": "personal", "checkUrl": "https://nankiv.example/health"}


def test_product_input_defaults_and_camel_case():
    p = ProductInput.model_validate(VALID)
    assert p.name == "Nankiv"
    assert p.timeout_ms == 10_000
    assert p.open_after == 2
    dumped = p.model_dump()
    assert dumped["checkUrl"] == "https://nankiv.example/health"
    assert dumped["sloTarget"] == 99.5
    assert "check_url" not in dumped


@pytest.mark.parametrize(
    "override",
    [
        {"checkUrl": "ftp://example.com"},
        {"checkUrl": "https://"},
        {"checkUrl": "https://user:pw@example.com"},
        {"name": ""},
        {"name": "x" * 61},
        {"kind": "enterprise"},
        {"note": "x" * 281},
        {"timeoutMs": 500},
        {"timeoutMs": 20_000},
        {"intervalMin": 2},
        {"openAfter": 0},
        {"resolveAfter": 6},
        {"sloTarget": 89.9},
        {"sloTarget": 100},
        {"expectedStatus": "2xx"},
        {"stack": ["a"] * 9},
        {"stack": ["x" * 31]},
        {"liveUrl": "javascript:alert(1)"},
        {"unknownField": 1},
    ],
)
def test_product_input_rejects(override):
    with pytest.raises(ValidationError):
        ProductInput.model_validate({**VALID, **override})


def test_product_input_cleans_optional_fields():
    p = ProductInput.model_validate(
        {
            **VALID,
            "liveUrl": "  ",
            "keyword": "",
            "stack": ["React", "react", " AWS "],
            "expectedStatus": "200, 301",
        }
    )
    assert p.live_url is None
    assert p.keyword is None
    assert p.stack == ["React", "AWS"]
    assert p.expected_status == "200,301"


def test_product_splits_into_config_and_live_state():
    product = Product.model_validate(
        {
            **VALID,
            "id": "01X",
            "createdAt": "2026-10-01T00:00:00Z",
            "updatedAt": "2026-10-01T00:00:00Z",
            "status": "DOWN",
            "PK": "PRODUCT#01X",
            "SK": "META",
        }
    )
    assert product.config().name == "Nankiv"
    assert product.live().status == "DOWN"


def test_utc_now_is_aware():
    from beacon_core.timeutil import utc_now

    assert utc_now().tzinfo is not None
