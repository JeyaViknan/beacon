"""Uptime, latency and error-budget maths (HANDOVER §8.5). Pure functions over rollups."""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from beacon_core.timeutil import rd_key, rh_key


@dataclass(frozen=True)
class Rollup:
    """Counters for one R5 / RH / RD bucket. Minutes are monitored minutes (paused excluded)."""

    up_min: int = 0
    total_min: int = 0
    down_min: int = 0
    lat_sum: int = 0
    lat_count: int = 0
    lat_max: int = 0

    @classmethod
    def from_item(cls, item: Mapping[str, object]) -> "Rollup":
        def num(key: str) -> int:
            # DynamoDB returns Decimal; go through str so any numeric type converts cleanly.
            return int(Decimal(str(item.get(key, 0))))

        return cls(
            up_min=num("upMin"),
            total_min=num("totalMin"),
            down_min=num("downMin"),
            lat_sum=num("latSum"),
            lat_count=num("latCount"),
            lat_max=num("latMax"),
        )

    def __add__(self, other: "Rollup") -> "Rollup":
        return Rollup(
            up_min=self.up_min + other.up_min,
            total_min=self.total_min + other.total_min,
            down_min=self.down_min + other.down_min,
            lat_sum=self.lat_sum + other.lat_sum,
            lat_count=self.lat_count + other.lat_count,
            lat_max=max(self.lat_max, other.lat_max),
        )


def combine(rollups: Iterable[Rollup]) -> Rollup:
    total = Rollup()
    for rollup in rollups:
        total = total + rollup
    return total


def uptime_ratio(rollup: Rollup) -> float | None:
    """``upMin / totalMin``; ``None`` when nothing was monitored in the window."""
    if rollup.total_min <= 0:
        return None
    return max(0.0, min(1.0, rollup.up_min / rollup.total_min))


def uptime_percent(rollup: Rollup, digits: int = 2) -> float | None:
    """Uptime as a percentage, rounded *down* so 99.996% never displays as 100.00%."""
    ratio = uptime_ratio(rollup)
    if ratio is None:
        return None
    scale = 10**digits
    return math.floor(ratio * 100 * scale) / scale


def avg_latency(rollup: Rollup) -> int | None:
    if rollup.lat_count <= 0:
        return None
    return round(rollup.lat_sum / rollup.lat_count)


def p95(values: Sequence[int]) -> int | None:
    """Nearest-rank 95th percentile."""
    if not values:
        return None
    ordered = sorted(values)
    rank = math.ceil(0.95 * len(ordered))
    return ordered[rank - 1]


@dataclass(frozen=True)
class ErrorBudget:
    slo_target: float
    monitored_min: int
    budget_min: float
    consumed_min: int
    remaining_min: float

    @property
    def remaining_ratio(self) -> float | None:
        """Share of the budget left (can go negative when the SLO is blown)."""
        if self.budget_min <= 0:
            return None
        return self.remaining_min / self.budget_min


def error_budget(slo_target: float, monitored_min: int, down_min: int) -> ErrorBudget:
    """``budget = (1 - slo/100) x monitored``; ``remaining = budget - down``."""
    budget = (1 - slo_target / 100) * monitored_min
    return ErrorBudget(
        slo_target=slo_target,
        monitored_min=monitored_min,
        budget_min=round(budget, 2),
        consumed_min=down_min,
        remaining_min=round(budget - down_min, 2),
    )


def hourly_keys(now: datetime, hours: int = 24) -> list[str]:
    """RH keys for the last ``hours`` hours, oldest first, ending with the current hour."""
    return [rh_key(now - timedelta(hours=h)) for h in range(hours - 1, -1, -1)]


def daily_keys(now: datetime, days: int = 30) -> list[str]:
    """RD keys for the last ``days`` IST days, oldest first, ending with today."""
    return [rd_key(now - timedelta(days=d)) for d in range(days - 1, -1, -1)]


def strip(keys: Sequence[str], buckets: Mapping[str, Rollup]) -> list[float | None]:
    """One uptime ratio per key (``None`` where nothing was monitored)."""
    return [uptime_ratio(buckets[k]) if k in buckets else None for k in keys]


@dataclass(frozen=True)
class SeriesPoint:
    t: str
    uptime: float | None
    lat_avg: int | None
    lat_max: int | None


def series(points: Iterable[tuple[str, Rollup]]) -> list[SeriesPoint]:
    """Chart points from (iso time, rollup) pairs, in the given order."""
    return [
        SeriesPoint(
            t=t,
            uptime=uptime_ratio(r),
            lat_avg=avg_latency(r),
            lat_max=r.lat_max if r.lat_count else None,
        )
        for t, r in points
    ]


def overall_state(counts: Mapping[str, int]) -> tuple[str, str]:
    """Header pill: (state, label) from status counts, e.g. ("down", "1 product down")."""
    down = counts.get("DOWN", 0)
    degraded = counts.get("DEGRADED", 0)
    if down:
        return "down", f"{down} product{'s' if down != 1 else ''} down"
    if degraded:
        return "degraded", f"{degraded} degraded"
    return "operational", "All systems operational"
