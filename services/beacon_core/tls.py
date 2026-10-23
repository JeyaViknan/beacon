"""TLS certificate expiry (HANDOVER §8.7), used by the daily maintenance run."""

import asyncio
import contextlib
import math
import ssl
from datetime import UTC, datetime

from beacon_core.ssrf import Resolver, resolve_target, system_resolver

THRESHOLDS = (14, 7)


async def fetch_cert_expiry(
    url: str, *, resolver: Resolver = system_resolver, timeout_s: float = 10.0
) -> datetime:
    """Open a verified TLS connection to the SSRF-checked IP and read the leaf's ``notAfter``."""
    target = await resolve_target(url, resolver)
    if target.scheme != "https":
        raise ValueError("not an https URL")
    context = ssl.create_default_context()
    async with asyncio.timeout(timeout_s):
        _, writer = await asyncio.open_connection(
            target.ip, target.port, ssl=context, server_hostname=target.host
        )
    try:
        cert = writer.get_extra_info("peercert") or {}
    finally:
        writer.close()
        with contextlib.suppress(OSError, ssl.SSLError):
            await writer.wait_closed()
    not_after = cert.get("notAfter")
    if not isinstance(not_after, str):
        raise ValueError("certificate has no notAfter")
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), UTC)


def days_left(expires_at: datetime, now: datetime) -> int:
    return math.floor((expires_at - now).total_seconds() / 86_400)


def tls_alert_level(days: int, already_alerted: int | None) -> tuple[bool, int | None]:
    """Alert once at <= 14 days and once more at <= 7. Returns (alert now?, level to store)."""
    if days > THRESHOLDS[0]:
        return False, None
    level = THRESHOLDS[1] if days <= THRESHOLDS[1] else THRESHOLDS[0]
    if already_alerted is None or level < already_alerted:
        return True, level
    return False, already_alerted
