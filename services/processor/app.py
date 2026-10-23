"""Processor Lambda (HANDOVER §8.3): probe messages -> state, rollups, incidents, alerts.

Per result: load product -> pure state machine -> one DynamoDB transaction -> publish alerts.
Idempotency (ADR 0011): the raw-check put inside the transaction is conditional on not existing,
so a redelivered message fails the transaction as a duplicate and is skipped as a whole.
Failures are reported per SQS record (partial batch response); poison messages reach the DLQ.
"""

import os
import time
from typing import Any

import httpx
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import (
    BatchProcessor,
    EventType,
    process_partial_response,
)
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import BotoCoreError, ClientError
from ulid import ULID

from beacon_core import aws
from beacon_core.alerts import degraded_alert, down_alert, recovered_alert, sns_publish_kwargs
from beacon_core.models import Alert, AlertEvent, CheckResult, ProbeMessage, Product, Settings
from beacon_core.repo_dynamo import ConflictError, DuplicateError
from beacon_core.state_machine import Evaluation, evaluate
from beacon_core.timeutil import parse_iso

logger = Logger()
tracer = Tracer()
metrics = Metrics()
batch = BatchProcessor(event_type=EventType.SQS)

MAX_ATTEMPTS = 3
SETTINGS_TTL_S = 60.0
_settings_cache: dict[str, tuple[float, Settings]] = {}


def settings() -> Settings:
    """Quorum etc., cached per container for a minute."""
    now = time.monotonic()
    cached = _settings_cache.get("settings")
    if cached is None or now - cached[0] > SETTINGS_TTL_S:
        cached = (now, aws.repo().get_settings())
        _settings_cache["settings"] = cached
    return cached[1]


def alerts_for(product: Product, ev: Evaluation) -> list[Alert]:
    out: list[Alert] = []
    for event in ev.alerts:
        if event is AlertEvent.DOWN and ev.opened is not None:
            out.append(down_alert(product, ev.opened))
        elif event is AlertEvent.RECOVERED and ev.resolved is not None:
            out.append(recovered_alert(product, ev.resolved))
        elif event is AlertEvent.DEGRADED:
            out.append(degraded_alert(product, product.recent_latencies))
    return out


def process_result(region: str, run_at_iso: str, result: CheckResult) -> list[Alert]:
    """Apply one result; retries on optimistic-lock conflicts (another region wrote first)."""
    repo = aws.repo()
    run_at = parse_iso(run_at_iso)
    for _ in range(MAX_ATTEMPTS):
        product = repo.get_product(result.product_id)
        if product is None:
            logger.info(
                "Result for unknown product (deleted?)", extra={"product_id": result.product_id}
            )
            return []
        ev = evaluate(
            product,
            region,
            result,
            run_at,
            incident_id=str(ULID()),
            quorum=settings().quorum,
        )
        if not ev.changed:
            logger.debug(
                "Nothing to apply", extra={"product_id": product.id, "outcome": ev.outcome}
            )
            return []
        try:
            repo.apply_evaluation(product, region, result, run_at, ev)
        except DuplicateError:
            logger.info("Duplicate result skipped", extra={"product_id": product.id})
            return []
        except ConflictError:
            logger.info("Version conflict, retrying", extra={"product_id": product.id})
            continue
        if ev.opened:
            metrics.add_metric(name="IncidentsOpened", unit=MetricUnit.Count, value=1)
            logger.warning(
                "Incident opened", extra={"product_id": product.id, "cause": ev.opened.cause}
            )
        if ev.resolved:
            metrics.add_metric(name="IncidentsResolved", unit=MetricUnit.Count, value=1)
            logger.info("Incident resolved", extra={"product_id": product.id})
        return alerts_for(product.model_copy(update=dict(ev.state)), ev)
    raise ConflictError(f"gave up after {MAX_ATTEMPTS} conflicts on {result.product_id}")


def publish(alerts: list[Alert]) -> None:
    """Publish after the state is committed. A failed publish is logged and counted, not retried
    through SQS (the redelivery would be a duplicate and skipped anyway). See ADR 0011."""
    topic = os.environ.get("PRODUCT_ALERTS_TOPIC_ARN")
    if not topic or not alerts:
        return
    email = settings().email_enabled
    for alert in alerts:
        try:
            aws.sns().publish(**sns_publish_kwargs(alert, topic, aws.app_url(), email=email))
        except (ClientError, BotoCoreError):
            logger.exception("Failed to publish alert", extra={"product_id": alert.product_id})
            metrics.add_metric(name="NotificationsFailed", unit=MetricUnit.Count, value=1)


def record_handler(record: SQSRecord) -> None:
    message = ProbeMessage.model_validate_json(record.body)
    logger.append_keys(correlation_id=record.message_id, region=message.region)
    for result in message.results:
        logger.append_keys(product_id=result.product_id)
        publish(process_result(message.region, message.run_at, result))
    logger.remove_keys(["product_id"])


def ping_healthchecks() -> None:
    """Dead-man's switch: healthchecks.io alerts Jeya if these pings stop for > 5 minutes."""
    url = aws.param("/beacon/healthchecks_ping_url")
    if not url:
        return
    try:
        httpx.get(url, timeout=3.0)
    except httpx.HTTPError:
        logger.warning("healthchecks.io ping failed")


@metrics.log_metrics
@tracer.capture_lambda_handler
@logger.inject_lambda_context
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    response = process_partial_response(
        event=event, record_handler=record_handler, processor=batch, context=context
    )
    if not response.get("batchItemFailures"):
        ping_healthchecks()
    return response
