from datetime import UTC, datetime
from decimal import Decimal

import pytest

from beacon_core.uptime import (
    Rollup,
    avg_latency,
    combine,
    daily_keys,
    error_budget,
    hourly_keys,
    overall_state,
    p95,
    series,
    strip,
    uptime_percent,
    uptime_ratio,
)


@pytest.mark.parametrize(
    ("up", "total", "expected"),
    [(0, 0, None), (60, 60, 1.0), (30, 60, 0.5), (0, 60, 0.0), (1439, 1440, 1439 / 1440)],
)
def test_uptime_ratio(up, total, expected):
    assert uptime_ratio(Rollup(up_min=up, total_min=total)) == expected


@pytest.mark.parametrize(
    ("up", "total", "expected"),
    [(43_197, 43_200, 99.99), (43_199, 43_200, 99.99), (1, 3, 33.33), (0, 0, None), (5, 5, 100.0)],
)
def test_uptime_percent_rounds_down(up, total, expected):
    assert uptime_percent(Rollup(up_min=up, total_min=total)) == expected


@pytest.mark.parametrize(
    ("slo", "monitored", "down", "budget", "remaining"),
    [
        (99.5, 43_200, 0, 216.0, 216.0),
        (99.5, 43_200, 216, 216.0, 0.0),
        (99.9, 43_200, 50, 43.2, -6.8),
        (99.0, 1_440, 4, 14.4, 10.4),
        (99.5, 0, 0, 0.0, 0.0),
    ],
)
def test_error_budget(slo, monitored, down, budget, remaining):
    eb = error_budget(slo, monitored, down)
    assert eb.budget_min == pytest.approx(budget)
    assert eb.remaining_min == pytest.approx(remaining)


def test_error_budget_remaining_ratio():
    assert error_budget(99.5, 43_200, 108).remaining_ratio == pytest.approx(0.5)
    assert error_budget(99.5, 0, 0).remaining_ratio is None


@pytest.mark.parametrize(
    ("values", "expected"),
    [([], None), ([100], 100), (list(range(1, 101)), 95), (list(range(1, 21)), 19), ([5, 1, 3], 5)],
)
def test_p95_nearest_rank(values, expected):
    assert p95(values) == expected


def test_combine_and_avg_latency():
    total = combine(
        [
            Rollup(up_min=5, total_min=5, lat_sum=1000, lat_count=5, lat_max=400),
            Rollup(up_min=3, total_min=5, down_min=2, lat_sum=600, lat_count=3, lat_max=900),
        ]
    )
    assert total == Rollup(
        up_min=8, total_min=10, down_min=2, lat_sum=1600, lat_count=8, lat_max=900
    )
    assert avg_latency(total) == 200
    assert avg_latency(Rollup()) is None


def test_rollup_from_dynamo_item_with_decimals():
    item = {"upMin": Decimal(4), "totalMin": Decimal(5), "latSum": Decimal(812), "latCount": 4}
    assert Rollup.from_item(item) == Rollup(up_min=4, total_min=5, lat_sum=812, lat_count=4)


def test_hourly_and_daily_keys():
    now = datetime(2026, 10, 24, 10, 30, tzinfo=UTC)
    hours = hourly_keys(now)
    assert len(hours) == 24
    assert hours[-1] == "RH#2026102410"
    assert hours[0] == "RH#2026102311"
    days = daily_keys(now, 3)
    assert days == ["RD#20261022", "RD#20261023", "RD#20261024"]


def test_strip_marks_missing_hours_as_none():
    keys = ["RH#2026102408", "RH#2026102409", "RH#2026102410"]
    buckets = {"RH#2026102409": Rollup(up_min=30, total_min=60)}
    assert strip(keys, buckets) == [None, 0.5, None]


def test_series_points():
    pts = series(
        [
            ("t1", Rollup(up_min=5, total_min=5, lat_sum=50, lat_count=5, lat_max=20)),
            ("t2", Rollup()),
        ]
    )
    assert pts[0].uptime == 1.0
    assert pts[0].lat_avg == 10
    assert pts[0].lat_max == 20
    assert pts[1].uptime is None
    assert pts[1].lat_max is None


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ({"UP": 4}, ("operational", "All systems operational")),
        ({}, ("operational", "All systems operational")),
        ({"UP": 3, "DOWN": 1}, ("down", "1 product down")),
        ({"DOWN": 2, "DEGRADED": 1}, ("down", "2 products down")),
        ({"UP": 1, "DEGRADED": 2}, ("degraded", "2 degraded")),
    ],
)
def test_overall_state(counts, expected):
    assert overall_state(counts) == expected
