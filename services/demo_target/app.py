"""Demo target Lambda (Function URL): 200 or 503 depending on SSM ``/beacon/demo/healthy``.

"Break demo target" in the app flips the parameter; Beacon then sees 503s and opens an incident.
The value is cached for 10 s, so a flip takes effect within one probe interval.
"""

from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from beacon_core import aws

logger = Logger()

DEMO_PARAM = "/beacon/demo/healthy"


def is_healthy() -> bool:
    value = aws.param(DEMO_PARAM, max_age=10.0)
    return (value or "true").strip().lower() != "false"


@logger.inject_lambda_context
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    healthy = is_healthy()
    return {
        "statusCode": 200 if healthy else 503,
        "headers": {"content-type": "text/plain; charset=utf-8", "cache-control": "no-store"},
        "body": "OK — Beacon demo target is healthy\n"
        if healthy
        else "Service Unavailable — demo target is broken on purpose\n",
    }
