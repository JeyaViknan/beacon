"""Maintenance Lambda, daily at 09:00 IST (HANDOVER §8.7).

1. TLS expiry: read each https product's certificate ``notAfter``, store it as ``certExpiresAt``,
   alert at <= 14 days and again at <= 7 days.
2. Daily summary push: "12 products · 99.98% up yesterday · 0 incidents".
Time-series cleanup needs no code: every time-series item carries a DynamoDB TTL.
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import BotoCoreError, ClientError

from beacon_core import aws
from beacon_core.alerts import daily_summary_alert, sns_publish_kwargs, tls_alert
from beacon_core.models import Alert, Product
from beacon_core.repo_dynamo import ConflictError
from beacon_core.ssrf import Resolver, system_resolver
from beacon_core.timeutil import IST, rd_key, to_iso, utc_now
from beacon_core.tls import days_left, fetch_cert_expiry, tls_alert_level
from beacon_core.uptime import combine, uptime_percent

logger = Logger()
tracer = Tracer()
metrics = Metrics()

RESOLVER: Resolver = system_resolver


def publish(alert: Alert) -> None:
    topic = os.environ.get("PRODUCT_ALERTS_TOPIC_ARN")
    if not topic:
        return
    try:
        aws.sns().publish(**sns_publish_kwargs(alert, topic, os.environ.get("APP_URL")))
    except (ClientError, BotoCoreError):
        logger.exception("Failed to publish alert", extra={"event": alert.event.value})


async def _expiries(products: list[Product]) -> list[tuple[Product, datetime | None]]:
    async def one(p: Product) -> tuple[Product, datetime | None]:
        try:
            return p, await fetch_cert_expiry(p.check_url, resolver=RESOLVER)
        except Exception:  # one bad host must not stop the others; logged with traceback
            logger.warning("TLS expiry check failed", extra={"product_id": p.id}, exc_info=True)
            return p, None

    return await asyncio.gather(*(one(p) for p in products))


def check_tls(products: list[Product], now: datetime) -> int:
    https = [p for p in products if p.enabled and p.check_url.startswith("https://")]
    alerts = 0
    for product, expires in asyncio.run(_expiries(https)):
        if expires is None:
            continue
        left = days_left(expires, now)
        alert_now, level = tls_alert_level(left, product.tls_alert_level)
        state = product.live().model_copy(
            update={"cert_expires_at": to_iso(expires), "tls_alert_level": level}
        )
        try:
            aws.repo().update_live(product, state, now)
        except ConflictError:
            logger.info(
                "Product changed during TLS check; will retry tomorrow",
                extra={"product_id": product.id},
            )
            continue
        if alert_now:
            publish(tls_alert(product, left))
            alerts += 1
    return alerts


def daily_summary(products: list[Product], now: datetime) -> dict[str, Any]:
    """Yesterday in IST: combined uptime over all products and incidents that started."""
    today_ist = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_ist = today_ist - timedelta(days=1)
    key = rd_key(yesterday_ist)
    repo = aws.repo()
    rollups = [repo.rollups(p.id, key, key).get(key) for p in products]
    total = combine(r for r in rollups if r is not None)
    incidents = repo.incidents_between(to_iso(yesterday_ist), to_iso(today_ist))
    uptime = uptime_percent(total)
    publish(daily_summary_alert(len(products), uptime, len(incidents)))
    return {"products": len(products), "uptime": uptime, "incidents": len(incidents)}


@metrics.log_metrics
@tracer.capture_lambda_handler
@logger.inject_lambda_context
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    now = utc_now()
    products = aws.repo().list_products()
    tls_alerts = check_tls(products, now)
    summary = daily_summary(products, now)
    result = {"tlsAlerts": tls_alerts, "summary": summary}
    logger.info("Maintenance complete", extra=result)
    return result
