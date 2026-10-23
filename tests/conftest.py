"""Shared fixtures. Environment is set at import time, before any handler module is imported."""

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


@dataclass
class AwsEnv:
    table: Any
    queue_url: str
    sqs: Any


@pytest.fixture
def aws(monkeypatch: pytest.MonkeyPatch) -> Iterator[AwsEnv]:
    with mock_aws():
        table = create_table()
        sqs = boto3.client("sqs", region_name=HOME_REGION)
        queue_url = sqs.create_queue(QueueName="beacon-results")["QueueUrl"]
        monkeypatch.setenv("RESULTS_QUEUE_URL", queue_url)
        yield AwsEnv(table=table, queue_url=queue_url, sqs=sqs)
