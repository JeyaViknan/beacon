"""Lazily created AWS clients and a small SSM parameter cache, shared by the handlers.

Clients are created on first use (not at import) so tests can wrap them in moto, and are reused
across warm invocations of the same container.
"""

import os
import time
from functools import cache
from typing import Any

import boto3

from beacon_core.repo_dynamo import Repo

PLACEHOLDER = "unset"  # value Terraform writes before Jeya sets the real secret

_params: dict[str, tuple[float, str | None]] = {}


def home_region() -> str:
    return os.environ.get("HOME_REGION") or os.environ.get("AWS_REGION", "ap-south-1")


@cache
def table() -> Any:
    return boto3.resource("dynamodb", region_name=home_region()).Table(os.environ["TABLE_NAME"])


@cache
def repo() -> Repo:
    return Repo(table())


@cache
def ssm() -> Any:
    return boto3.client("ssm", region_name=home_region())


@cache
def sns() -> Any:
    return boto3.client("sns", region_name=home_region())


def param(name: str, *, max_age: float = 300.0) -> str | None:
    """SSM parameter (decrypted), cached per container; ``None`` if missing or a placeholder."""
    now = time.monotonic()
    cached = _params.get(name)
    if cached is not None and now - cached[0] < max_age:
        return cached[1]
    try:
        raw = ssm().get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    except ssm().exceptions.ParameterNotFound:
        raw = None
    value = None if raw in (None, "", PLACEHOLDER) else str(raw)
    _params[name] = (now, value)
    return value


def app_url() -> str | None:
    """Public URL of the app for links in emails/PagerDuty (env for tests, else SSM)."""
    return os.environ.get("APP_URL") or param("/beacon/app_url", max_age=3600)


def reset() -> None:
    """Forget clients and cached parameters (tests, or after rotating a secret)."""
    for fn in (table, repo, ssm, sns):
        fn.cache_clear()
    _params.clear()
