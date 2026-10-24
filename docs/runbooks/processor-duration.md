# Runbook: beacon-processor-duration

**Fires when:** `beacon-processor` **p95 duration > 20 s** for two 5-minute periods. The timeout is 30 s.

## What it means
Batches are getting close to the timeout. A timeout fails the whole batch, which is then retried and can end in the DLQ.

## User impact
Not yet visible, but it's an early warning before queue age and DLQ alarms.

## How to check
1. **X-Ray:** CloudWatch → X-Ray traces → filter `service("beacon-processor")`, sort by duration. Look for the slow segment:
   - `DynamoDB TransactWriteItems`: throttling or contention. See [ddb-throttles](ddb-throttles.md).
   - `SNS Publish`: SNS slowness.
   - `hc-ping.com`: healthchecks.io slow; the ping has a 3 s timeout.
2. **Conflict retries:** count `Version conflict, retrying` in the logs. Many regions writing the same products cause repeated re-reads.
   ```bash
   aws logs filter-log-events --log-group-name /aws/lambda/beacon-processor --start-time $(( ($(date +%s) - 3600) * 1000 )) --filter-pattern '"Version conflict"' --query 'length(events)'
   ```

## How to fix
- **Throttling:** see [ddb-throttles](ddb-throttles.md).
- **Too many results per batch** (many products × regions): lower the event source `batch_size` (10 → 5) in `infra/main/lambdas.tf`, or raise processor memory to 512 MB (more CPU; still free at this volume).
- **External ping slow:** it's already capped at 3 s; consider pinging only every Nth batch.

## Escalate
If timeouts appear (`Task timed out`), switch to [processor-errors](processor-errors.md) and [dlq-not-empty](dlq-not-empty.md).
