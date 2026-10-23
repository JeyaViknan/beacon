"""Monitor snapshot: the control-plane / data-plane contract (ADR 0004).

The API writes one compact ``CONFIG/MONITORS`` item whenever products change. Probes read only
that item (cached for 30 s), so a probe run costs one read regardless of how many products exist,
and adding or removing a product never needs a redeploy.
"""

import time
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from beacon_core.models import MonitorSnapshot, MonitorSpec, Product
from beacon_core.timeutil import epoch_minute, to_iso

SNAPSHOT_KEY = {"PK": "CONFIG", "SK": "MONITORS"}
CACHE_SECONDS = 30.0


def build_snapshot(products: Iterable[Product], version: int, now: datetime) -> MonitorSnapshot:
    monitors = [
        MonitorSpec(
            id=p.id,
            check_url=p.check_url,
            method=p.method,
            expected_status=p.expected_status,
            keyword=p.keyword,
            timeout_ms=p.timeout_ms,
            interval_min=p.interval_min,
            enabled=p.enabled,
        )
        for p in sorted(products, key=lambda p: p.id)
    ]
    return MonitorSnapshot(version=version, updated_at=to_iso(now), monitors=monitors)


def due_monitors(snapshot: MonitorSnapshot, run_at: datetime) -> list[MonitorSpec]:
    """Enabled monitors whose interval divides the current minute."""
    minute = epoch_minute(run_at)
    return [m for m in snapshot.monitors if m.enabled and minute % m.interval_min == 0]


class SnapshotCache:
    """Per-container cache so warm probe invocations skip the read for 30 s."""

    def __init__(
        self,
        load: Callable[[], dict[str, Any] | None],
        ttl: float = CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._load = load
        self._ttl = ttl
        self._clock = clock
        self._value: MonitorSnapshot | None = None
        self._loaded_at = float("-inf")

    def get(self) -> MonitorSnapshot:
        now = self._clock()
        if self._value is None or now - self._loaded_at >= self._ttl:
            item = self._load()
            self._value = (
                MonitorSnapshot.model_validate(item)
                if item
                else MonitorSnapshot(version=0, updated_at="1970-01-01T00:00:00Z", monitors=[])
            )
            self._loaded_at = now
        return self._value
