"""Time helpers.

Storage is always UTC ISO-8601 with a trailing ``Z`` and second precision. Humans see IST.
Time-series buckets (R5, RH) are keyed in UTC; the daily bucket (RD) is keyed by the IST calendar
date, because "a day" in the daily bars and the daily summary means Jeya's day, not UTC's.
"""

from datetime import UTC, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(dt: datetime) -> str:
    """Format an aware datetime as ``2026-10-24T10:15:00Z``."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime; use timezone-aware datetimes only")
    return dt.astimezone(UTC).strftime(_ISO_FMT)


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string (``Z`` or offset) into an aware UTC datetime."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp without timezone: {value!r}")
    return dt.astimezone(UTC)


def epoch_minute(dt: datetime) -> int:
    """Whole minutes since the Unix epoch; the state machine steps once per value."""
    return int(dt.timestamp()) // 60


def floor_minute(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(second=0, microsecond=0)


def r5_key(dt: datetime) -> str:
    """5-minute rollup sort key, e.g. ``R5#202610241015``."""
    d = floor_minute(dt)
    d = d.replace(minute=d.minute - d.minute % 5)
    return f"R5#{d:%Y%m%d%H%M}"


def rh_key(dt: datetime) -> str:
    """Hourly rollup sort key (UTC hour), e.g. ``RH#2026102410``."""
    return f"RH#{dt.astimezone(UTC):%Y%m%d%H}"


def rd_key(dt: datetime) -> str:
    """Daily rollup sort key (IST calendar date), e.g. ``RD#20261024``."""
    return f"RD#{dt.astimezone(IST):%Y%m%d}"


def ttl_after(dt: datetime, *, hours: float) -> int:
    """Epoch seconds for DynamoDB TTL, ``hours`` after ``dt``."""
    return int((dt + timedelta(hours=hours)).timestamp())


def format_duration(seconds: float) -> str:
    """Compact human duration: ``45s``, ``6m 12s``, ``2h 14m``, ``3d 4h``."""
    total = max(0, int(seconds))
    days, rem = divmod(total, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_ist(dt: datetime) -> str:
    """``24 Oct 15:45 IST``: used in alert bodies and the daily summary."""
    return f"{dt.astimezone(IST):%d %b %H:%M} IST"
