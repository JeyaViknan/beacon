"""Notifier Lambda (HANDOVER §10): SNS product alert -> Web Push (VAPID) + PagerDuty Events v2."""

import hashlib
import json
import os
from typing import Any

import httpx
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from pywebpush import WebPushException, webpush

from beacon_core import aws
from beacon_core.models import Alert, AlertEvent, Severity

logger = Logger()
tracer = Tracer()
metrics = Metrics()

PAGERDUTY_URL = "https://events.pagerduty.com/v2/enqueue"
GONE = {404, 410}


class DeliveryError(Exception):
    """A channel failed in a way worth retrying (Lambda async retry + notifier-errors alarm)."""


def subscription_key(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()


def push_payload(alert: Alert) -> str:
    return json.dumps(
        {"title": alert.title, "body": alert.body, "url": alert.url, "tag": alert.tag}
    )


def send_push(alert: Alert) -> tuple[int, int]:
    """Push to every subscribed device. Returns (sent, failed). Dead subscriptions are removed."""
    private_key = aws.param("/beacon/vapid_private_key")
    subject = aws.param("/beacon/vapid_subject")
    if not private_key or not subject:
        logger.warning("Web Push not configured (VAPID key/subject missing)")
        return 0, 0
    repo = aws.repo()
    sent = failed = 0
    for sub in repo.list_subscriptions():
        info = {"endpoint": sub["endpoint"], "keys": sub["keys"]}
        try:
            webpush(
                subscription_info=info,
                data=push_payload(alert),
                vapid_private_key=private_key,
                vapid_claims={
                    "sub": subject
                },  # pywebpush mutates claims, so a fresh dict each time
                ttl=3600,
                headers={"Urgency": "high" if alert.severity is Severity.CRITICAL else "normal"},
                timeout=5,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in GONE:
                repo.delete_subscription(sub["SK"])
                logger.info("Removed expired push subscription", extra={"status": status})
            else:
                failed += 1
                logger.warning("Push failed", extra={"status": status})
    return sent, failed


def pagerduty_body(alert: Alert, routing_key: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "routing_key": routing_key,
        "event_action": alert.pagerduty_action,
        "dedup_key": alert.dedup_key,
    }
    if alert.pagerduty_action == "trigger":
        body["payload"] = {
            "summary": f"{alert.title} — {alert.body}",
            "source": "beacon",
            "severity": "critical" if alert.severity is Severity.CRITICAL else "warning",
            "component": alert.product_id,
            "custom_details": {"event": alert.event.value},
        }
        app_url = os.environ.get("APP_URL")
        if app_url:
            body["links"] = [
                {"href": f"{app_url.rstrip('/')}{alert.url}", "text": "Open in Beacon"}
            ]
    return body


def send_pagerduty(alert: Alert) -> bool:
    """Returns True if sent, False if not configured. Raises ``DeliveryError`` on failure."""
    routing_key = aws.param("/beacon/pagerduty_routing_key")
    if not routing_key or not alert.pagerduty_action or not alert.dedup_key:
        return False
    try:
        resp = httpx.post(PAGERDUTY_URL, json=pagerduty_body(alert, routing_key), timeout=5.0)
    except httpx.HTTPError as exc:
        raise DeliveryError("PagerDuty unreachable") from exc
    if resp.status_code >= 300:
        raise DeliveryError(f"PagerDuty returned HTTP {resp.status_code}")
    return True


def deliver(alert: Alert) -> dict[str, Any]:
    settings = aws.repo().get_settings()
    report: dict[str, Any] = {
        "event": alert.event.value,
        "pushSent": 0,
        "pushFailed": 0,
        "pagerduty": False,
    }

    if settings.push_enabled and alert.event is not AlertEvent.ACKNOWLEDGED:
        sent, failed = send_push(alert)
        report.update(pushSent=sent, pushFailed=failed)
        metrics.add_metric(name="NotificationsSent", unit=MetricUnit.Count, value=sent)
        if failed:
            metrics.add_metric(name="NotificationsFailed", unit=MetricUnit.Count, value=failed)

    wants_page = alert.severity is Severity.CRITICAL or alert.event is AlertEvent.ACKNOWLEDGED
    if settings.pagerduty_enabled and wants_page:
        try:
            report["pagerduty"] = send_pagerduty(alert)
        except DeliveryError:
            metrics.add_metric(name="NotificationsFailed", unit=MetricUnit.Count, value=1)
            raise
        if report["pagerduty"]:
            metrics.add_metric(name="NotificationsSent", unit=MetricUnit.Count, value=1)

    if report["pushFailed"] and not report["pushSent"]:
        # Every device failed: worth a retry and an alarm. Partial failures are only counted,
        # so a retry never re-notifies devices that already got the alert.
        raise DeliveryError("all push deliveries failed")
    return report


@metrics.log_metrics
@tracer.capture_lambda_handler
@logger.inject_lambda_context
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    reports = []
    for record in event.get("Records", []):
        sns = record["Sns"]
        logger.append_keys(correlation_id=sns.get("MessageId"))
        alert = Alert.model_validate_json(sns["Message"])
        logger.append_keys(product_id=alert.product_id)
        report = deliver(alert)
        logger.info("Alert delivered", extra=report)
        reports.append(report)
    return {"delivered": reports}
