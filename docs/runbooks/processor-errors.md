# Runbook: beacon-processor-errors

**Fires when:** `beacon-processor` reports `Errors ≥ 1` in 5 minutes.

## What it means
The processor raised an unhandled exception. With partial batch responses, only the failing SQS messages are retried; after 5 receives a message moves to the DLQ (`beacon-dlq-not-empty` fires).

Per-record failures that are handled (reported as `batchItemFailures`) do **not** count as Lambda errors. This alarm means the whole invocation failed: a crash, a timeout, or an error outside the record loop.

## User impact
Results are delayed or retried. Statuses and alerts lag behind reality. The healthchecks.io heartbeat stops while batches fail.

## How to check
```bash
aws logs tail /aws/lambda/beacon-processor --since 30m --filter-pattern '?ERROR ?Traceback ?"Task timed out"'
```

| Log shows | Meaning |
|---|---|
| `ProvisionedThroughputExceededException` | DynamoDB throttling. See [ddb-throttles](ddb-throttles.md). |
| `ConflictError: gave up after 3 conflicts` | Several regions are writing the same product at once. Rare; retries usually win. |
| `ValidationError` on `ProbeMessage` | A malformed message (bad deploy of the probe). It will end up in the DLQ. |
| `Task timed out after 30.00 seconds` | See [processor-duration](processor-duration.md). |
| `AccessDenied` | IAM drift: re-run the deploy. |

Also check the dashboard: if *Errors* line up with a deploy, it's the deploy.

## How to fix
- **Transient** (throttles, conflicts): usually self-heals. Retries are safe because each result is idempotent (ADR 0011).
- **Code bug:** `git revert` the commit and approve the deploy. Then redrive the DLQ ([dlq-not-empty](dlq-not-empty.md)).

## Escalate
Errors for more than 15 minutes, or any message in the DLQ, mean you'll write an RCA.
