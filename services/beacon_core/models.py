"""Pydantic v2 models shared by every Lambda.

Python attributes are snake_case; JSON (API and DynamoDB) is camelCase via an alias generator,
so the wire format matches HANDOVER §3.3 / §7 exactly.
"""

import re
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

Kind = Literal["personal", "client"]


class Status(StrEnum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    PAUSED = "PAUSED"
    UNKNOWN = "UNKNOWN"


class IncidentState(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertEvent(StrEnum):
    DOWN = "DOWN"
    RECOVERED = "RECOVERED"
    DEGRADED = "DEGRADED"
    TLS_EXPIRING = "TLS_EXPIRING"
    DAILY_SUMMARY = "DAILY_SUMMARY"
    TEST = "TEST"


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        extra="ignore",
    )


# ---------------------------------------------------------------------------
# Expected-status ranges: "200-399", "200", "200,204,301-302"
# ---------------------------------------------------------------------------

_RANGE_PART = re.compile(r"^\s*(\d{3})\s*(?:-\s*(\d{3})\s*)?$")


def parse_status_ranges(spec: str) -> list[tuple[int, int]]:
    """Parse an expected-status spec into inclusive ``(low, high)`` ranges."""
    ranges: list[tuple[int, int]] = []
    for part in spec.split(","):
        match = _RANGE_PART.match(part)
        if not match:
            raise ValueError(f"invalid status range {part.strip()!r}")
        low = int(match.group(1))
        high = int(match.group(2) or low)
        if not (100 <= low <= high <= 599):
            raise ValueError(f"status range out of bounds: {part.strip()!r}")
        ranges.append((low, high))
    return ranges


def status_matches(code: int, spec: str) -> bool:
    return any(low <= code <= high for low, high in parse_status_ranges(spec))


def _check_http_url(value: str, field: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"{field} must start with http:// or https://")
    if not parts.hostname:
        raise ValueError(f"{field} must include a host")
    if parts.username or parts.password:
        raise ValueError(f"{field} must not contain credentials")
    return value


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


class ProductInput(CamelModel):
    """What the user edits (HANDOVER §3.3). Unknown fields are rejected."""

    model_config = ConfigDict(**{**CamelModel.model_config, "extra": "forbid"})

    name: str = Field(min_length=1, max_length=60)
    kind: Kind
    note: str = Field(default="", max_length=280)
    check_url: str = Field(max_length=2048)
    method: Literal["GET", "HEAD"] = "GET"
    expected_status: str = Field(default="200-399", max_length=60)
    keyword: str | None = Field(default=None, max_length=200)
    timeout_ms: int = Field(default=10_000, ge=1_000, le=15_000)
    interval_min: Literal[1, 5] = 1
    latency_warn_ms: int = Field(default=2_000, ge=100, le=60_000)
    open_after: int = Field(default=2, ge=1, le=5)
    resolve_after: int = Field(default=2, ge=1, le=5)
    slo_target: float = Field(default=99.5, ge=90, le=99.99)
    live_url: str | None = Field(default=None, max_length=2048)
    github_url: str | None = Field(default=None, max_length=2048)
    stack: list[str] = Field(default_factory=list, max_length=8)
    sort_order: int = Field(default=100, ge=0, le=99_999)

    @field_validator("name", "note", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("check_url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return _check_http_url(value, "checkUrl")

    @field_validator("live_url", "github_url", "keyword", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("live_url", "github_url")
    @classmethod
    def _optional_url(cls, value: str | None) -> str | None:
        return None if value is None else _check_http_url(value, "url")

    @field_validator("expected_status")
    @classmethod
    def _expected_status(cls, value: str) -> str:
        parse_status_ranges(value)
        return value.replace(" ", "")

    @field_validator("stack")
    @classmethod
    def _stack(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            tag = tag.strip()
            if not 1 <= len(tag) <= 30:
                raise ValueError("stack tags must be 1-30 characters")
            if tag.lower() not in (t.lower() for t in cleaned):
                cleaned.append(tag)
        return cleaned


class RegionState(CamelModel):
    ok: bool
    at: str
    latency_ms: int | None = None
    http_code: int | None = None
    error: str | None = None


class EvalBase(CamelModel):
    """Counters as they were before this minute's step, so a later region can re-evaluate."""

    failures: int = 0
    successes: int = 0
    slow: int = 0
    streak_since: str | None = None


class LiveState(CamelModel):
    """Fields the processor owns (HANDOVER §7, product live-state)."""

    status: Status = Status.UNKNOWN
    status_since: str | None = None
    last_check_at: str | None = None
    last_latency_ms: int | None = None
    last_http_code: int | None = None
    last_error: str | None = None
    regions: dict[str, RegionState] = Field(default_factory=dict)
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    consecutive_slow: int = 0
    last_eval_minute: int = 0
    last_eval_failing: bool | None = None
    eval_base: EvalBase | None = None
    streak_since: str | None = None
    open_incident_sk: str | None = None
    recent_latencies: list[int] = Field(default_factory=list)
    cert_expires_at: str | None = None
    tls_alert_level: int | None = None


LIVE_FIELDS: tuple[str, ...] = tuple(LiveState.model_fields)


class Product(LiveState, ProductInput):
    """A stored product: user config + identity + live state."""

    model_config = ConfigDict(**{**CamelModel.model_config, "extra": "ignore"})

    id: str
    enabled: bool = True
    created_at: str
    updated_at: str
    version: int = 0

    def config(self) -> ProductInput:
        return ProductInput.model_validate(self.model_dump(include=set(ProductInput.model_fields)))

    def live(self) -> LiveState:
        return LiveState.model_validate(self.model_dump(include=set(LIVE_FIELDS)))


# ---------------------------------------------------------------------------
# Checks, probe messages and the monitor snapshot
# ---------------------------------------------------------------------------


class CheckResult(CamelModel):
    product_id: str
    ok: bool
    http_code: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    keyword_ok: bool | None = None


class ProbeMessage(CamelModel):
    """One SQS message per probe run (HANDOVER §8.1)."""

    region: str
    run_at: str
    results: list[CheckResult]


class MonitorSpec(CamelModel):
    """Only what a probe needs to run a check; published in the CONFIG/MONITORS snapshot."""

    id: str
    check_url: str
    method: Literal["GET", "HEAD"] = "GET"
    expected_status: str = "200-399"
    keyword: str | None = None
    timeout_ms: int = 10_000
    interval_min: Literal[1, 5] = 1
    enabled: bool = True


class MonitorSnapshot(CamelModel):
    version: int
    updated_at: str
    monitors: list[MonitorSpec]


# ---------------------------------------------------------------------------
# Incidents and settings
# ---------------------------------------------------------------------------


class TimelineEntry(CamelModel):
    at: str
    event: str
    detail: str | None = None


class Incident(CamelModel):
    product_id: str
    sk: str
    id: str
    product_name: str = ""
    state: IncidentState = IncidentState.OPEN
    started_at: str
    acknowledged_at: str | None = None
    resolved_at: str | None = None
    duration_sec: int | None = None
    cause: str
    first_error: str | None = None
    failing_regions: list[str] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)


class Settings(CamelModel):
    """``CONFIG/SETTINGS``. ``quorum=None`` means ceil(fresh regions / 2)."""

    quorum: int | None = Field(default=None, ge=1, le=3)
    push_enabled: bool = True
    email_enabled: bool = True
    pagerduty_enabled: bool = True


class Alert(CamelModel):
    """The payload published to the ``beacon-product-alerts`` SNS topic."""

    event: AlertEvent
    severity: Severity
    product_id: str | None = None
    title: str
    body: str
    url: str = "/"
    tag: str = "beacon"
    dedup_key: str | None = None
    pagerduty_action: Literal["trigger", "acknowledge", "resolve"] | None = None
