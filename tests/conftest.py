"""Shared fixtures. Environment is set at import time, before any handler module is imported."""

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import boto3
import pytest
from moto import mock_aws

HOME_REGION = "ap-south-1"

os.environ.update(
    {
        "AWS_DEFAULT_REGION": HOME_REGION,
        "AWS_REGION": HOME_REGION,
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "POWERTOOLS_TRACE_DISABLED": "true",
        "POWERTOOLS_METRICS_NAMESPACE": "Beacon",
        "POWERTOOLS_SERVICE_NAME": "beacon-test",
        "POWERTOOLS_DEV": "false",
        "TABLE_NAME": "beacon",
        "HOME_REGION": HOME_REGION,
    }
)


@dataclass
class FakeContext:
    function_name: str = "beacon-test"
    memory_limit_in_mb: int = 256
    invoked_function_arn: str = "arn:aws:lambda:ap-south-1:123456789012:function:beacon-test"
    aws_request_id: str = "req-0001"

    def get_remaining_time_in_millis(self) -> int:
        return 30_000


@pytest.fixture
def lambda_context() -> FakeContext:
    return FakeContext()


def create_table(name: str = "beacon") -> Any:
    ddb = boto3.resource("dynamodb", region_name=HOME_REGION)
    table = ddb.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 15, "WriteCapacityUnits": 15},
    )
    table.wait_until_exists()
    return table


SSM_PLACEHOLDERS = {
    "/beacon/admin_password_hash": "unset",
    "/beacon/jwt_secret": "unset",
    "/beacon/vapid_private_key": "unset",
    "/beacon/vapid_subject": "unset",
    "/beacon/pagerduty_routing_key": "unset",
    "/beacon/healthchecks_ping_url": "unset",
    "/beacon/demo/healthy": "true",
}


@dataclass
class AwsEnv:
    table: Any
    queue_url: str
    sqs: Any
    ssm: Any
    topic_arn: str
    published: list[dict[str, Any]]

    def set_param(self, name: str, value: str) -> None:
        from beacon_core import aws as beacon_aws

        self.ssm.put_parameter(Name=name, Value=value, Type="SecureString", Overwrite=True)
        beacon_aws._params.clear()

    def alerts(self) -> list[dict[str, Any]]:
        """Alert payloads (the notifier's view) of everything published to SNS."""
        return [json.loads(json.loads(p["Message"])["default"]) for p in self.published]


@pytest.fixture
def aws(monkeypatch: pytest.MonkeyPatch) -> Iterator[AwsEnv]:
    from beacon_core import aws as beacon_aws

    with mock_aws():
        beacon_aws.reset()
        table = create_table()
        sqs = boto3.client("sqs", region_name=HOME_REGION)
        queue_url = sqs.create_queue(QueueName="beacon-results")["QueueUrl"]
        ssm = boto3.client("ssm", region_name=HOME_REGION)
        for name, value in SSM_PLACEHOLDERS.items():
            kind = (
                "String"
                if name in ("/beacon/demo/healthy", "/beacon/vapid_subject")
                else "SecureString"
            )
            ssm.put_parameter(Name=name, Value=value, Type=kind)
        topic_arn = boto3.client("sns", region_name=HOME_REGION).create_topic(
            Name="beacon-product-alerts"
        )["TopicArn"]
        monkeypatch.setenv("RESULTS_QUEUE_URL", queue_url)
        monkeypatch.setenv("PRODUCT_ALERTS_TOPIC_ARN", topic_arn)
        monkeypatch.setenv("APP_URL", "https://beacon.example.cloudfront.net")

        published: list[dict[str, Any]] = []
        client = beacon_aws.sns()
        real_publish = client.publish

        def spy(**kwargs: Any) -> Any:
            published.append(kwargs)
            return real_publish(**kwargs)

        monkeypatch.setattr(client, "publish", spy)
        yield AwsEnv(
            table=table,
            queue_url=queue_url,
            sqs=sqs,
            ssm=ssm,
            topic_arn=topic_arn,
            published=published,
        )
        beacon_aws.reset()


def product_item(**overrides: Any) -> dict[str, Any]:
    """A valid Product as camelCase JSON."""
    base: dict[str, Any] = {
        "id": "01PRODUCT",
        "name": "Nankiv",
        "kind": "personal",
        "checkUrl": "https://nankiv.example/health",
        "createdAt": "2026-10-01T00:00:00Z",
        "updatedAt": "2026-10-01T00:00:00Z",
    }
    base.update(overrides)
    return base
