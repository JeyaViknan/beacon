"""Pure builders for API response bodies (ProductSummary, ProductDetail, series)."""

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from beacon_core.models import Incident, Product, Status
from beacon_core.timeutil import IST, r5_key, rd_key, rh_key, to_iso
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
)

Range = Literal["24h", "7d", "30d"]

STATUS_ORDER = {
    Status.DOWN: 0,
    Status.DEGRADED: 1,
    Status.UP: 2,
    Status.UNKNOWN: 3,
    Status.PAUSED: 4,
}

# Internal state-machine bookkeeping that clients never need.
_INTERNAL = {"evalBase", "lastEvalMinute", "lastEvalFailing", "streakSince", "tlsAlertLevel"}


def public_product(product: Product) -> dict[str, Any]:
    data = product.model_dump(mode="json")
    return {k: v for k, v in data.items() if k not in _INTERNAL}


def window_bounds(now: datetime) -> dict[str, tuple[str, str]]:
    """Inclusive SK bounds for the rollup queries behind each stat."""
    return {
        "r5": (r5_key(now - timedelta(hours=24) + timedelta(minutes=5)), r5_key(now)),
        "rh": (rh_key(now - timedelta(hours=167)), rh_key(now)),
        "rh24": (rh_key(now - timedelta(hours=23)), rh_key(now)),
        "rd": (rd_key(now - timedelta(days=29)), rd_key(now)),
    }


def product_summary(
    product: Product, rd: Mapping[str, Rollup], rh: Mapping[str, Rollup], now: datetime
) -> dict[str, Any]:
    days = daily_keys(now, 30)
    return {
        "id": product.id,
        "name": product.name,
        "kind": product.kind,
        "note": product.note,
        "status": product.status.value,
        "statusSince": product.status_since,
        "enabled": product.enabled,
        "lastCheckAt": product.last_check_at,
        "lastLatencyMs": product.last_latency_ms,
        "lastHttpCode": product.last_http_code,
        "lastError": product.last_error,
        "sortOrder": product.sort_order,
        "liveUrl": product.live_url,
        "openIncident": product.open_incident_sk is not None,
        "uptime30d": uptime_percent(combine(rd[k] for k in days if k in rd)),
        "strip24h": strip(hourly_keys(now), rh),
    }


def sort_summaries(summaries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Down -> Degraded -> Up -> Unknown -> Paused, then sortOrder, then name."""
    return sorted(
        summaries,
        key=lambda s: (
            STATUS_ORDER.get(Status(s["status"]), 9),
            s["sortOrder"],
            s["name"].lower(),
        ),
    )


def summary_counts(products: Iterable[Product]) -> dict[str, Any]:
    counts = {s.value: 0 for s in Status}
    for p in products:
        counts[p.status.value] += 1
    state, label = overall_state(counts)
    return {
        "up": counts["UP"],
        "degraded": counts["DEGRADED"],
        "down": counts["DOWN"],
        "paused": counts["PAUSED"],
        "unknown": counts["UNKNOWN"],
        "total": sum(counts.values()),
        "state": state,
        "label": label,
    }


def product_detail(
    product: Product,
    r5: Mapping[str, Rollup],
    rh: Mapping[str, Rollup],
    rd: Mapping[str, Rollup],
    open_incident: Incident | None,
) -> dict[str, Any]:
    day = combine(r5.values())
    month = combine(rd.values())
    budget = error_budget(product.slo_target, month.total_min, month.down_min)
    return {
        "product": public_product(product),
        "stats": {
            "uptime24h": uptime_percent(day),
            "uptime7d": uptime_percent(combine(rh.values())),
            "uptime30d": uptime_percent(month),
            "avgLatency24h": avg_latency(day),
            "p95Latency1h": p95(product.recent_latencies),
            "sloTarget": product.slo_target,
            "errorBudget": {
                "budgetMin": budget.budget_min,
                "consumedMin": budget.consumed_min,
                "remainingMin": budget.remaining_min,
                "remainingRatio": budget.remaining_ratio,
                "monitoredMin": budget.monitored_min,
            },
        },
        "openIncident": open_incident.model_dump(mode="json") if open_incident else None,
    }


def series_keys(rng: Range, now: datetime) -> list[tuple[str, datetime]]:
    """(bucket key, bucket start) pairs for a chart range, oldest first."""
    if rng == "24h":
        end = now.astimezone(UTC).replace(second=0, microsecond=0)
        end = end.replace(minute=end.minute - end.minute % 5)
        starts = [end - timedelta(minutes=5 * i) for i in range(287, -1, -1)]
        return [(r5_key(s), s) for s in starts]
    if rng == "7d":
        end = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        starts = [end - timedelta(hours=i) for i in range(167, -1, -1)]
        return [(rh_key(s), s) for s in starts]
    today = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    starts = [today - timedelta(days=i) for i in range(29, -1, -1)]
    return [(rd_key(s), s) for s in starts]


def series_points(rng: Range, buckets: Mapping[str, Rollup], now: datetime) -> list[dict[str, Any]]:
    pairs = [(to_iso(start), buckets.get(key, Rollup())) for key, start in series_keys(rng, now)]
    return [
        {"t": p.t, "uptime": p.uptime, "latAvg": p.lat_avg, "latMax": p.lat_max}
        for p in series(pairs)
    ]
