"""Alert construction and SNS publishing (HANDOVER §10).

One ``Alert`` model travels through SNS. The ``default``/``lambda`` message is the JSON payload for
the notifier; the ``email`` message is human-readable text. Message attributes (``event``,
``severity``, ``productId``) drive the email subscription's filter policy.
"""

import json
import re
from collections.abc import Sequence
from typing import Any

from beacon_core.models import Alert, AlertEvent, Incident, Product, Severity
from beacon_core.state_machine import IncidentOpened, IncidentResolved, parse_incident_sk
from beacon_core.timeutil import format_duration


def _seconds(ms: float) -> str:
    """``2000`` -> ``2 s``; ``3400`` -> ``3.4 s``."""
    value = ms / 1000
    return f"{value:.0f} s" if value == int(value) else f"{value:.1f} s"


def down_alert(product: Product, opened: IncidentOpened) -> Alert:
    regions = ", ".join(opened.failing_regions)
    body = f"{opened.cause} ({regions})" if regions else opened.cause
    return Alert(
        event=AlertEvent.DOWN,
        severity=Severity.CRITICAL,
        product_id=product.id,
        title=f"🔴 DOWN: {product.name}",
        body=body,
        url=f"/p/{product.id}",
        tag=product.id,
        dedup_key=opened.id,
        pagerduty_action="trigger",
    )


def recovered_alert(product: Product, resolved: IncidentResolved) -> Alert:
    _, incident_id = parse_incident_sk(resolved.sk)
    duration = format_duration(resolved.duration_sec)
    if resolved.cause == "recovered":
        title, body = f"🟢 RECOVERED: {product.name}", f"down for {duration}"
    else:
        title, body = (
            f"⏸️ PAUSED: {product.name}",
            f"incident closed after {duration} ({resolved.cause})",
        )
    return Alert(
        event=AlertEvent.RECOVERED,
        severity=Severity.CRITICAL,
        product_id=product.id,
        title=title,
        body=body,
        url=f"/p/{product.id}",
        tag=product.id,
        dedup_key=incident_id,
        pagerduty_action="resolve",
    )


def degraded_alert(product: Product, latencies: Sequence[int]) -> Alert:
    recent = list(latencies[-3:]) or [product.last_latency_ms or 0]
    avg = sum(recent) / len(recent)
    return Alert(
        event=AlertEvent.DEGRADED,
        severity=Severity.WARNING,
        product_id=product.id,
        title=f"🟠 SLOW: {product.name}",
        body=f"{_seconds(avg)} avg (limit {_seconds(product.latency_warn_ms)})",
        url=f"/p/{product.id}",
        tag=product.id,
    )


def acknowledged_alert(incident: Incident) -> Alert:
    """PagerDuty-only: mirrors an in-app acknowledgement. No push, no email."""
    return Alert(
        event=AlertEvent.ACKNOWLEDGED,
        severity=Severity.INFO,
        product_id=incident.product_id,
        title=f"Acknowledged: {incident.product_name}",
        body=incident.cause,
        url=f"/p/{incident.product_id}",
        tag=incident.product_id,
        dedup_key=incident.id,
        pagerduty_action="acknowledge",
    )


def tls_alert(product: Product, days_left: int) -> Alert:
    unit = "day" if days_left == 1 else "days"
    return Alert(
        event=AlertEvent.TLS_EXPIRING,
        severity=Severity.WARNING,
        product_id=product.id,
        title=f"🔐 TLS expiring: {product.name}",
        body=f"{days_left} {unit} left",
        url=f"/p/{product.id}",
        tag=f"tls-{product.id}",
    )


def daily_summary_alert(products: int, uptime_pct: float | None, incidents: int) -> Alert:
    uptime = "no data" if uptime_pct is None else f"{uptime_pct:.2f}% up yesterday"
    noun = "incident" if incidents == 1 else "incidents"
    return Alert(
        event=AlertEvent.DAILY_SUMMARY,
        severity=Severity.INFO,
        title="Beacon daily summary",
        body=f"{products} products · {uptime} · {incidents} {noun}",
        url="/",
        tag="daily-summary",
    )


def make_test_alert() -> Alert:
    return Alert(
        event=AlertEvent.TEST,
        severity=Severity.INFO,
        title="🔔 Beacon test notification",
        body="If you can read this, alerts reach you.",
        url="/settings",
        tag="test",
    )


_NON_PRINTABLE = re.compile(r"[^\x20-\x7e]+")


def email_subject(alert: Alert) -> str:
    """SNS subjects must be printable ASCII and < 100 characters, so emoji are dropped."""
    text = _NON_PRINTABLE.sub("", f"[Beacon] {alert.title} - {alert.body}")
    text = re.sub(r"\s+", " ", text).replace("[Beacon] :", "[Beacon]").strip()
    return text[:99]


def email_body(alert: Alert, app_url: str | None) -> str:
    lines = [f"{alert.title} — {alert.body}", ""]
    if alert.dedup_key and alert.event is AlertEvent.DOWN:
        lines.append(f"Incident: {alert.dedup_key}")
    if app_url:
        lines.append(f"Open in Beacon: {app_url.rstrip('/')}{alert.url}")
    lines += ["", "— Beacon uptime monitor"]
    return "\n".join(lines)


def sns_publish_kwargs(
    alert: Alert, topic_arn: str, app_url: str | None, *, email: bool = True
) -> dict[str, Any]:
    """``email`` feeds the email subscription's filter policy (Settings -> email on/off)."""
    payload = alert.model_dump_json()
    attributes: dict[str, dict[str, str]] = {
        "event": {"DataType": "String", "StringValue": alert.event.value},
        "severity": {"DataType": "String", "StringValue": alert.severity.value},
        "email": {"DataType": "String", "StringValue": "on" if email else "off"},
    }
    if alert.product_id:
        attributes["productId"] = {"DataType": "String", "StringValue": alert.product_id}
    return {
        "TopicArn": topic_arn,
        "Subject": email_subject(alert),
        "MessageStructure": "json",
        "Message": json.dumps(
            {"default": payload, "lambda": payload, "email": email_body(alert, app_url)}
        ),
        "MessageAttributes": attributes,
    }
