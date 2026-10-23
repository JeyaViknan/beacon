"""Probe Lambda (HANDOVER §8.1).

Every minute: read the monitor snapshot (cached 30 s), run the checks that are due, and send
exactly one SQS message to the home-region results queue, even when nothing is due, so the
processor's dead-man's-switch ping keeps proving the whole pipeline is alive.
"""

import asyncio
import os
import time
from datetime import datetime
from functools import cache
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from beacon_core.checks import run_checks
from beacon_core.models import ProbeMessage
from beacon_core.snapshot import SNAPSHOT_KEY, SnapshotCache, due_monitors
from beacon_core.ssrf import Resolver, system_resolver
from beacon_core.timeutil import floor_minute, parse_iso, to_iso, utc_now

logger = Logger()
tracer = Tracer()
metrics = Metrics()

RESOLVER: Resolver = system_resolver


@cache
def _table() -> Any:
    region = os.environ["HOME_REGION"]
    return boto3.resource("dynamodb", region_name=region).Table(os.environ["TABLE_NAME"])


@cache
def _sqs() -> Any:
    return boto3.client("sqs", region_name=os.environ["HOME_REGION"])


def _load_snapshot() -> dict[str, Any] | None:
    item: dict[str, Any] | None = _table().get_item(Key=SNAPSHOT_KEY).get("Item")
    return item


snapshot_cache = SnapshotCache(_load_snapshot)


def run_time(event: Any) -> datetime:
    """The scheduled minute (Scheduler passes ``<aws.scheduler.scheduled-time>``), else now."""
    raw = event.get("scheduledTime") if isinstance(event, dict) else None
    try:
        when = parse_iso(raw) if isinstance(raw, str) else utc_now()
    except ValueError:
        when = utc_now()
    return floor_minute(when)


@metrics.log_metrics
@tracer.capture_lambda_handler
@logger.inject_lambda_context
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    region = os.environ.get("PROBE_REGION") or os.environ["AWS_REGION"]
    run_at = run_time(event)
    logger.append_keys(region=region, correlation_id=context.aws_request_id)
    started = time.perf_counter()

    snapshot = snapshot_cache.get()
    due = due_monitors(snapshot, run_at)
    budget = float(os.environ.get("PROBE_BUDGET_S", "45"))
    results, skipped = asyncio.run(run_checks(due, budget_s=budget, resolver=RESOLVER))
    if skipped:
        logger.warning("Probe budget exhausted; checks skipped", extra={"skipped": skipped})

    message = ProbeMessage(region=region, run_at=to_iso(run_at), results=results)
    _sqs().send_message(
        QueueUrl=os.environ["RESULTS_QUEUE_URL"], MessageBody=message.model_dump_json()
    )

    failed = [r for r in results if not r.ok]
    for r in failed:
        logger.info("Check failed", extra={"product_id": r.product_id, "error": r.error})
    metrics.add_metric(name="ChecksRun", unit=MetricUnit.Count, value=len(results))
    metrics.add_metric(name="ChecksFailed", unit=MetricUnit.Count, value=len(failed))
    metrics.add_metric(
        name="ProbeRunSeconds", unit=MetricUnit.Seconds, value=time.perf_counter() - started
    )
    summary = {
        "region": region,
        "runAt": message.run_at,
        "snapshotVersion": snapshot.version,
        "checked": len(results),
        "failed": len(failed),
        "skipped": len(skipped),
    }
    logger.info("Probe run complete", extra=summary)
    return summary
