"""Table-driven tests for the incident state machine (HANDOVER §8.5)."""

from datetime import UTC, datetime, timedelta

import pytest

from beacon_core.models import AlertEvent, CheckResult, IncidentState, Product, Status
from beacon_core.state_machine import (
    PAUSE_CAUSE,
    Evaluation,
    RollupDelta,
    acknowledge,
    effective_quorum,
    evaluate,
    incident_sk,
    new_incident,
    parse_incident_sk,
    pause,
    resolve_incident,
    resume,
)

T0 = datetime(2026, 10, 24, 10, 0, tzinfo=UTC)
HOME = "ap-south-1"
SG = "ap-southeast-1"
US = "us-east-1"


def make_product(**overrides: object) -> Product:
    base: dict[str, object] = {
        "id": "01PRODUCT",
        "name": "Nankiv",
        "kind": "personal",
        "checkUrl": "https://example.com/health",
        "createdAt": "2026-10-01T00:00:00Z",
        "updatedAt": "2026-10-01T00:00:00Z",
    }
    base.update(overrides)
    return Product.model_validate(base)


def result(ok: bool, latency: int = 200, error: str | None = None) -> CheckResult:
    return CheckResult(
        product_id="01PRODUCT",
        ok=ok,
        http_code=200 if ok else 502,
        latency_ms=latency,
        error=None if ok else (error or "HTTP 502"),
    )


class Runner:
    """Feeds results through the state machine and carries state forward like the processor."""

    def __init__(self, product: Product, quorum: int | None = None) -> None:
        self.product = product
        self.quorum = quorum
        self.counter = 0
        self.history: list[Evaluation] = []

    def step(
        self, minute: int, ok: bool, *, region: str = HOME, latency: int = 200, second: int = 0
    ) -> Evaluation:
        self.counter += 1
        ev = evaluate(
            self.product,
            region,
            result(ok, latency),
            T0 + timedelta(minutes=minute, seconds=second),
            incident_id=f"INC{self.counter:03d}",
            quorum=self.quorum,
        )
        if ev.changed:
            self.product = self.product.model_copy(update=dict(ev.state))
        self.history.append(ev)
        return ev

    def run(self, verdicts: str, **kwargs: object) -> list[Evaluation]:
        """``verdicts`` like "FFOO": F = fail, O = ok, S = ok but slow; one per minute."""
        out = []
        for minute, v in enumerate(verdicts):
            latency = 5_000 if v == "S" else 200
            out.append(self.step(minute, v != "F", latency=latency, **kwargs))  # type: ignore[arg-type]
        return out

    @property
    def alerts(self) -> list[AlertEvent]:
        return [a for ev in self.history for a in ev.alerts]


# --- opening and resolving ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("open_after", "verdicts", "expect_open_at"),
    [
        (1, "F", 0),
        (2, "FF", 1),
        (2, "OFF", 2),
        (3, "FFF", 2),
        (5, "FFFFF", 4),
        (2, "F", None),
        (2, "FOFOF", None),
        (3, "FFOFF", None),
    ],
)
def test_incident_opens_after_consecutive_failures(open_after, verdicts, expect_open_at):
    r = Runner(make_product(openAfter=open_after))
    evs = r.run(verdicts)
    opened_at = [i for i, ev in enumerate(evs) if ev.opened is not None]
    assert opened_at == ([] if expect_open_at is None else [expect_open_at])
    if expect_open_at is not None:
        assert r.product.status is Status.DOWN
        assert r.alerts == [AlertEvent.DOWN]


@pytest.mark.parametrize(
    ("resolve_after", "verdicts", "expect_resolve_at"),
    [
        (1, "FFO", 2),
        (2, "FFOO", 3),
        (2, "FFOFOO", 5),
        (3, "FFOOO", 4),
        (2, "FFO", None),
        (2, "FFOFO", None),
    ],
)
def test_incident_resolves_after_consecutive_successes(resolve_after, verdicts, expect_resolve_at):
    r = Runner(make_product(openAfter=2, resolveAfter=resolve_after))
    evs = r.run(verdicts)
    resolved_at = [i for i, ev in enumerate(evs) if ev.resolved is not None]
    assert resolved_at == ([] if expect_resolve_at is None else [expect_resolve_at])
    expected_status = Status.UP if expect_resolve_at is not None else Status.DOWN
    assert r.product.status is expected_status


def test_incident_times_use_first_failure_and_first_success():
    r = Runner(make_product(openAfter=2, resolveAfter=2))
    evs = r.run("OFFFOO")
    opened = evs[2].opened
    assert opened is not None
    assert opened.started_at == "2026-10-24T10:01:00Z"
    assert opened.cause == "HTTP 502"
    assert opened.failing_regions == (HOME,)
    assert opened.sk == incident_sk("2026-10-24T10:01:00Z", "INC003")
    resolved = evs[5].resolved
    assert resolved is not None
    assert resolved.resolved_at == "2026-10-24T10:04:00Z"
    assert resolved.duration_sec == 180
    assert r.product.status_since == "2026-10-24T10:04:00Z"
    assert r.product.open_incident_sk is None


def test_no_second_incident_while_one_is_open():
    r = Runner(make_product(openAfter=1))
    evs = r.run("FFFF")
    assert sum(1 for ev in evs if ev.opened) == 1
    assert r.alerts == [AlertEvent.DOWN]


def test_failure_counters_reset_on_success():
    r = Runner(make_product(openAfter=3))
    r.run("FFO")
    assert r.product.consecutive_failures == 0
    assert r.product.consecutive_successes == 1


# --- idempotency and ordering ---------------------------------------------------------------


def test_redelivered_result_is_a_duplicate():
    r = Runner(make_product(openAfter=1))
    first = r.step(0, ok=False)
    again = r.step(0, ok=False)
    assert first.opened is not None
    assert again.outcome == "duplicate"
    assert not again.changed
    assert again.alerts == ()
    assert r.product.consecutive_failures == 1


def test_late_result_for_an_evaluated_minute_does_not_step():
    r = Runner(make_product(openAfter=1))
    r.step(5, ok=True, region=HOME)
    late = r.step(3, ok=False, region=SG)
    assert late.outcome == "late"
    assert late.rollup == RollupDelta()
    assert late.alerts == ()
    assert r.product.consecutive_successes == 1
    assert r.product.regions[SG].ok is False


def test_disabled_product_is_ignored():
    ev = evaluate(make_product(enabled=False), HOME, result(False), T0, incident_id="X")
    assert ev.outcome == "paused"
    assert not ev.changed


# --- multi-region quorum and freshness ------------------------------------------------------


@pytest.mark.parametrize(
    ("fresh", "configured", "expected"),
    [(0, None, 1), (1, None, 1), (2, None, 1), (3, None, 2), (3, 1, 1), (3, 3, 3), (1, 3, 1)],
)
def test_effective_quorum(fresh, configured, expected):
    assert effective_quorum(fresh, configured) == expected


@pytest.mark.parametrize(
    ("region_verdicts", "expect_failing"),
    [
        ({HOME: True, SG: True, US: True}, False),
        ({HOME: False, SG: True, US: True}, False),
        ({HOME: False, SG: False, US: True}, True),
        ({HOME: False, SG: False, US: False}, True),
    ],
)
def test_three_region_quorum_needs_two_failures(region_verdicts, expect_failing):
    r = Runner(make_product(openAfter=1))
    for second, region in enumerate(region_verdicts):  # warm up: every region reported OK
        r.step(0, True, region=region, second=second)
    ev = None
    for second, (region, ok) in enumerate(region_verdicts.items()):
        ev = r.step(1, ok, region=region, second=second)
    assert ev is not None
    assert ev.failing is expect_failing
    assert (r.product.status is Status.DOWN) is expect_failing


def test_stale_region_is_ignored():
    r = Runner(make_product(openAfter=1))
    r.step(0, ok=False, region=SG)  # SG fails once, then goes quiet
    r.step(1, ok=True, region=HOME)
    ev = r.step(5, ok=True, region=HOME)  # SG is 5 minutes old: stale for a 1-minute interval
    assert ev.failing is False
    assert set(r.product.regions) == {HOME, SG}


def test_same_minute_reevaluation_does_not_double_step():
    r = Runner(make_product(openAfter=2))
    r.step(0, ok=True, region=HOME)
    r.step(0, ok=True, region=SG, second=5)
    assert r.product.consecutive_successes == 1  # one minute, one step

    r.step(1, ok=True, region=HOME)
    ev = r.step(1, ok=False, region=SG, second=5)  # 1 of 2 fresh failing, quorum 1 -> failing
    assert ev.outcome == "reevaluated"
    assert ev.failing is True
    assert r.product.consecutive_failures == 1
    assert r.product.consecutive_successes == 0
    assert ev.rollup == RollupDelta(up_min=-1, total_min=0, down_min=1)


def test_cold_start_single_region_decides_alone():
    # Before other regions have reported, fresh regions = 1, so quorum is capped at 1.
    r = Runner(make_product(openAfter=1), quorum=2)
    ev = r.step(0, ok=False, region=HOME)
    assert ev.opened is not None


def test_configured_quorum_two_requires_two_regions():
    r = Runner(make_product(openAfter=1), quorum=2)
    r.step(0, ok=True, region=HOME)
    r.step(0, ok=True, region=SG, second=5)
    r.step(1, ok=False, region=HOME)
    r.step(1, ok=True, region=SG, second=5)
    assert r.product.status is not Status.DOWN
    r.step(2, ok=False, region=HOME)
    ev = r.step(2, ok=False, region=SG, second=5)
    assert ev.opened is not None
    assert ev.opened.failing_regions == (HOME, SG)


# --- uptime rollup deltas -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("interval", "ok", "expected"),
    [
        (1, True, RollupDelta(up_min=1, total_min=1, down_min=0)),
        (1, False, RollupDelta(up_min=0, total_min=1, down_min=1)),
        (5, True, RollupDelta(up_min=5, total_min=5, down_min=0)),
        (5, False, RollupDelta(up_min=0, total_min=5, down_min=5)),
    ],
)
def test_rollup_delta_per_evaluation(interval, ok, expected):
    ev = evaluate(make_product(intervalMin=interval), HOME, result(ok), T0, incident_id="X")
    assert ev.rollup == expected


def test_same_minute_same_verdict_adds_nothing():
    r = Runner(make_product())
    r.step(0, ok=True, region=HOME)
    ev = r.step(0, ok=True, region=SG, second=3)
    assert ev.rollup == RollupDelta()


# --- latency / degraded ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verdicts", "final_status", "alerts"),
    [
        ("SS", Status.UP, []),
        ("SSS", Status.DEGRADED, [AlertEvent.DEGRADED]),
        ("SSSS", Status.DEGRADED, [AlertEvent.DEGRADED]),
        ("SSSO", Status.UP, [AlertEvent.DEGRADED]),
        ("SSOSS", Status.UP, []),
        ("SSSOSSS", Status.DEGRADED, [AlertEvent.DEGRADED, AlertEvent.DEGRADED]),
    ],
)
def test_degraded_after_three_slow_evaluations(verdicts, final_status, alerts):
    r = Runner(make_product(latencyWarnMs=2_000))
    r.run(verdicts)
    assert r.product.status is final_status
    assert r.alerts == alerts


def test_failure_while_degraded_resets_slow_counter():
    r = Runner(make_product(openAfter=3))
    r.run("SSF")
    assert r.product.consecutive_slow == 0


def test_recent_latencies_is_a_bounded_ring_buffer():
    r = Runner(make_product())
    for minute in range(70):
        r.step(minute, ok=True, latency=minute)
    assert len(r.product.recent_latencies) == 60
    assert r.product.recent_latencies[0] == 10
    assert r.product.recent_latencies[-1] == 69


def test_first_success_sets_up_from_unknown():
    r = Runner(make_product())
    assert r.product.status is Status.UNKNOWN
    r.step(0, ok=True)
    assert r.product.status is Status.UP
    assert r.alerts == []


# --- pause / resume -------------------------------------------------------------------------


def test_pause_with_open_incident_resolves_it():
    r = Runner(make_product(openAfter=1))
    r.run("FF")
    state, resolved = pause(r.product, T0 + timedelta(minutes=10))
    assert state.status is Status.PAUSED
    assert state.open_incident_sk is None
    assert resolved is not None
    assert resolved.cause == PAUSE_CAUSE
    assert resolved.duration_sec == 600


def test_pause_without_incident_resolves_nothing():
    state, resolved = pause(make_product(), T0)
    assert state.status is Status.PAUSED
    assert resolved is None


def test_resume_starts_from_a_clean_slate():
    r = Runner(make_product(openAfter=3))
    r.run("FF")
    state = resume(r.product, T0 + timedelta(minutes=5))
    assert state.status is Status.UNKNOWN
    assert state.regions == {}
    assert state.consecutive_failures == 0
    assert state.last_eval_minute == 0


# --- incidents ------------------------------------------------------------------------------


def _incident() -> tuple[Runner, Evaluation]:
    r = Runner(make_product(openAfter=1, resolveAfter=1))
    ev = r.step(0, ok=False)
    return r, ev


def test_new_incident_has_opened_timeline_entry():
    r, ev = _incident()
    assert ev.opened is not None
    inc = new_incident(r.product, ev.opened)
    assert inc.state is IncidentState.OPEN
    assert inc.product_name == "Nankiv"
    assert [t.event for t in inc.timeline] == ["opened"]


def test_acknowledge_is_idempotent_and_refuses_resolved():
    r, ev = _incident()
    assert ev.opened is not None
    inc = new_incident(r.product, ev.opened)
    acked = acknowledge(inc, T0 + timedelta(minutes=1))
    assert acked.state is IncidentState.ACKNOWLEDGED
    assert acknowledge(acked, T0 + timedelta(minutes=2)) == acked

    resolved_ev = r.step(1, ok=True)
    assert resolved_ev.resolved is not None
    done = resolve_incident(acked, resolved_ev.resolved)
    assert done.state is IncidentState.RESOLVED
    assert done.duration_sec == 60
    assert [t.event for t in done.timeline] == ["opened", "acknowledged", "resolved"]
    with pytest.raises(ValueError, match="already resolved"):
        acknowledge(done, T0)


def test_acknowledged_incident_still_resolves():
    r, _ = _incident()
    ev = r.step(1, ok=True)
    assert ev.resolved is not None
    assert ev.alerts == (AlertEvent.RECOVERED,)


@pytest.mark.parametrize("bad", ["CHECK#2026#x", "INC", "R5#202610241015"])
def test_parse_incident_sk_rejects_other_keys(bad):
    with pytest.raises(ValueError):
        parse_incident_sk(bad)


def test_parse_incident_sk_roundtrip():
    sk = incident_sk("2026-10-24T10:00:00Z", "01ULID")
    assert parse_incident_sk(sk) == ("2026-10-24T10:00:00Z", "01ULID")
