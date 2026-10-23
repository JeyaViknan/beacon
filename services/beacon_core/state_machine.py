"""Incident state machine (HANDOVER §8.5).

Pure functions only: no I/O, no clock, no randomness. The processor passes in everything
(the stored product, one region's result, the run time, a pre-generated incident id) and
persists whatever ``Evaluation`` says. That is what makes every rule table-testable.

Key ideas:
- Freshness: a region's latest result counts while it is younger than 2 x intervalMin.
- Quorum: the product is failing when failing fresh regions >= quorum
  (default ceil(fresh / 2), never more than the number of fresh regions).
- Counters step once per minute. A second region reporting for the same minute
  re-evaluates from the counters saved before that minute's step (``eval_base``),
  so it can change the verdict without double-counting.
- Uptime rollups get a delta per evaluation, so per-minute verdicts are counted once
  per product, not once per region.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from beacon_core.models import (
    AlertEvent,
    CheckResult,
    EvalBase,
    Incident,
    IncidentState,
    LiveState,
    Product,
    RegionState,
    Status,
    TimelineEntry,
)
from beacon_core.timeutil import epoch_minute, parse_iso, to_iso

SLOW_EVALS_FOR_DEGRADED = 3
RECENT_LATENCIES = 60
PAUSE_CAUSE = "paused by user"


@dataclass(frozen=True)
class RollupDelta:
    up_min: int = 0
    total_min: int = 0
    down_min: int = 0


@dataclass(frozen=True)
class IncidentOpened:
    sk: str
    id: str
    started_at: str
    cause: str
    first_error: str | None
    failing_regions: tuple[str, ...]


@dataclass(frozen=True)
class IncidentResolved:
    sk: str
    resolved_at: str
    duration_sec: int
    cause: str = "recovered"


@dataclass(frozen=True)
class Evaluation:
    state: LiveState
    outcome: str  # "evaluated" | "reevaluated" | "late" | "duplicate" | "paused"
    failing: bool = False
    rollup: RollupDelta = field(default_factory=RollupDelta)
    opened: IncidentOpened | None = None
    resolved: IncidentResolved | None = None
    alerts: tuple[AlertEvent, ...] = ()

    @property
    def changed(self) -> bool:
        """False when nothing should be written (duplicate delivery or paused product)."""
        return self.outcome not in ("duplicate", "paused")


def incident_sk(started_at: str, incident_id: str) -> str:
    return f"INC#{started_at}#{incident_id}"


def parse_incident_sk(sk: str) -> tuple[str, str]:
    """``INC#<isoStart>#<ulid>`` -> (isoStart, ulid)."""
    prefix, started_at, incident_id = sk.split("#", 2)
    if prefix != "INC":
        raise ValueError(f"not an incident sort key: {sk!r}")
    return started_at, incident_id


def effective_quorum(fresh_regions: int, configured: int | None) -> int:
    if fresh_regions <= 0:
        return 1
    wanted = configured if configured is not None else math.ceil(fresh_regions / 2)
    return max(1, min(wanted, fresh_regions))


def evaluate(
    product: Product,
    region: str,
    result: CheckResult,
    run_at: datetime,
    *,
    incident_id: str,
    quorum: int | None = None,
) -> Evaluation:
    """Apply one region's result for one product and decide what changes."""
    state = product.live()
    if not product.enabled:
        return Evaluation(state=state, outcome="paused")

    run_iso = to_iso(run_at)
    previous = state.regions.get(region)
    if previous is not None and parse_iso(previous.at) >= run_at:
        return Evaluation(state=state, outcome="duplicate")

    regions = {
        **state.regions,
        region: RegionState(
            ok=result.ok,
            at=run_iso,
            latency_ms=result.latency_ms,
            http_code=result.http_code,
            error=result.error,
        ),
    }
    latencies = state.recent_latencies
    if result.ok and result.latency_ms is not None:
        latencies = [*latencies, result.latency_ms][-RECENT_LATENCIES:]
    state = state.model_copy(
        update={
            "regions": regions,
            "last_check_at": run_iso,
            "last_latency_ms": result.latency_ms,
            "last_http_code": result.http_code,
            "last_error": result.error,
            "recent_latencies": latencies,
        }
    )

    run_minute = epoch_minute(run_at)
    if run_minute < state.last_eval_minute:
        # A result for a minute that is already evaluated (late delivery). Record the region's
        # latest view but do not touch counters or open/resolve anything.
        return Evaluation(state=state, outcome="late")

    window = timedelta(minutes=2 * product.interval_min)
    fresh = {r: s for r, s in regions.items() if run_at - parse_iso(s.at) < window}
    failing_regions = sorted(r for r, s in fresh.items() if not s.ok)
    failing = len(failing_regions) >= effective_quorum(len(fresh), quorum)

    stepped = run_minute > state.last_eval_minute
    if stepped:
        base = EvalBase(
            failures=state.consecutive_failures,
            successes=state.consecutive_successes,
            slow=state.consecutive_slow,
            streak_since=state.streak_since,
        )
    else:
        base = state.eval_base or EvalBase()

    ok_latencies = [s.latency_ms for s in fresh.values() if s.ok and s.latency_ms is not None]
    eval_latency = sum(ok_latencies) / len(ok_latencies) if ok_latencies else None
    slow = not failing and eval_latency is not None and eval_latency > product.latency_warn_ms

    if failing:
        failures, successes, slow_count = base.failures + 1, 0, 0
        streak_since = base.streak_since if base.failures > 0 and base.streak_since else run_iso
    else:
        failures, successes = 0, base.successes + 1
        slow_count = base.slow + 1 if slow else 0
        streak_since = base.streak_since if base.successes > 0 and base.streak_since else run_iso

    status, status_since = state.status, state.status_since
    open_sk = state.open_incident_sk
    alerts: list[AlertEvent] = []
    opened: IncidentOpened | None = None
    resolved: IncidentResolved | None = None

    if failing:
        if open_sk is None and failures >= product.open_after:
            open_sk = incident_sk(streak_since, incident_id)
            first_failing = regions[failing_regions[0]] if failing_regions else regions[region]
            cause = first_failing.error or "check failed"
            opened = IncidentOpened(
                sk=open_sk,
                id=incident_id,
                started_at=streak_since,
                cause=cause,
                first_error=result.error,
                failing_regions=tuple(failing_regions),
            )
            status, status_since = Status.DOWN, streak_since
            alerts.append(AlertEvent.DOWN)
    elif open_sk is not None:
        if successes >= product.resolve_after:
            started_at, _ = parse_incident_sk(open_sk)
            duration = int((parse_iso(streak_since) - parse_iso(started_at)).total_seconds())
            resolved = IncidentResolved(
                sk=open_sk, resolved_at=streak_since, duration_sec=max(0, duration)
            )
            open_sk = None
            status, status_since = Status.UP, streak_since
            alerts.append(AlertEvent.RECOVERED)
    else:
        new_status = Status.DEGRADED if slow_count >= SLOW_EVALS_FOR_DEGRADED else Status.UP
        if new_status != status:
            if new_status is Status.DEGRADED:
                alerts.append(AlertEvent.DEGRADED)
            status, status_since = new_status, run_iso

    step = product.interval_min
    if stepped:
        up = 0 if failing else step
        rollup = RollupDelta(up_min=up, total_min=step, down_min=step - up)
    elif state.last_eval_failing is None or state.last_eval_failing == failing:
        rollup = RollupDelta()
    else:
        # Same minute, verdict flipped: move that minute between up and down.
        up = -step if failing else step
        rollup = RollupDelta(up_min=up, total_min=0, down_min=-up)

    state = state.model_copy(
        update={
            "status": status,
            "status_since": status_since,
            "consecutive_failures": failures,
            "consecutive_successes": successes,
            "consecutive_slow": slow_count,
            "last_eval_minute": run_minute,
            "last_eval_failing": failing,
            "eval_base": base,
            "streak_since": streak_since,
            "open_incident_sk": open_sk,
        }
    )
    return Evaluation(
        state=state,
        outcome="evaluated" if stepped else "reevaluated",
        failing=failing,
        rollup=rollup,
        opened=opened,
        resolved=resolved,
        alerts=tuple(alerts),
    )


def _reset_counters(state: LiveState, **update: object) -> LiveState:
    return state.model_copy(
        update={
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "consecutive_slow": 0,
            "last_eval_failing": None,
            "eval_base": None,
            "streak_since": None,
            "open_incident_sk": None,
            **update,
        }
    )


def pause(product: Product, now: datetime) -> tuple[LiveState, IncidentResolved | None]:
    """Pause monitoring. An open incident is resolved with cause "paused by user"."""
    state = product.live()
    resolved: IncidentResolved | None = None
    if state.open_incident_sk:
        started_at, _ = parse_incident_sk(state.open_incident_sk)
        resolved = IncidentResolved(
            sk=state.open_incident_sk,
            resolved_at=to_iso(now),
            duration_sec=max(0, int((now - parse_iso(started_at)).total_seconds())),
            cause=PAUSE_CAUSE,
        )
    return _reset_counters(state, status=Status.PAUSED, status_since=to_iso(now)), resolved


def resume(product: Product, now: datetime) -> LiveState:
    """Resume monitoring from a clean slate; status is UNKNOWN until the next check."""
    return _reset_counters(
        product.live(),
        status=Status.UNKNOWN,
        status_since=to_iso(now),
        regions={},
        last_eval_minute=0,
    )


def new_incident(product: Product, opened: IncidentOpened) -> Incident:
    detail = f"{opened.cause} ({', '.join(opened.failing_regions)})"
    return Incident(
        product_id=product.id,
        product_name=product.name,
        sk=opened.sk,
        id=opened.id,
        state=IncidentState.OPEN,
        started_at=opened.started_at,
        cause=opened.cause,
        first_error=opened.first_error,
        failing_regions=list(opened.failing_regions),
        timeline=[TimelineEntry(at=opened.started_at, event="opened", detail=detail)],
    )


def acknowledge(incident: Incident, now: datetime) -> Incident:
    """Mark an incident acknowledged. Idempotent; a resolved incident cannot be acknowledged."""
    if incident.state is IncidentState.RESOLVED:
        raise ValueError("incident is already resolved")
    if incident.state is IncidentState.ACKNOWLEDGED:
        return incident
    at = to_iso(now)
    return incident.model_copy(
        update={
            "state": IncidentState.ACKNOWLEDGED,
            "acknowledged_at": at,
            "timeline": [*incident.timeline, TimelineEntry(at=at, event="acknowledged")],
        }
    )


def resolve_incident(incident: Incident, resolved: IncidentResolved) -> Incident:
    return incident.model_copy(
        update={
            "state": IncidentState.RESOLVED,
            "resolved_at": resolved.resolved_at,
            "duration_sec": resolved.duration_sec,
            "timeline": [
                *incident.timeline,
                TimelineEntry(at=resolved.resolved_at, event="resolved", detail=resolved.cause),
            ],
        }
    )
