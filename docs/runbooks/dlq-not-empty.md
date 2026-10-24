# Runbook: beacon-dlq-not-empty

**Fires when:** `beacon-results-dlq` has **at least 1 visible message**.

## What it means
A probe message failed processing **5 times** and was set aside so it can't block the rest (a "poison message").

## User impact
That run's results were **never applied**: a gap in uptime and latency data, and possibly a missed DOWN or RECOVERED transition.

## How to check
1. **Peek at one message** (it stays in the DLQ; visibility timeout 0):
   ```bash
   DLQ=$(aws sqs get-queue-url --queue-name beacon-results-dlq --query QueueUrl --output text)
   aws sqs receive-message --queue-url "$DLQ" --max-number-of-messages 1 --visibility-timeout 0 --query 'Messages[0].Body' --output text
   ```
2. **Find the failure:** search processor logs near the message's `runAt`:
   ```bash
   aws logs tail /aws/lambda/beacon-processor --since 2h --filter-pattern '?ERROR ?Traceback'
   ```

## How to fix
1. Fix the cause first: usually revert a bad deploy, or correct data.
2. **Redrive** the messages back to the main queue:
   ```bash
   aws sqs start-message-move-task --source-arn "$(aws sqs get-queue-attributes --queue-url "$DLQ" --attribute-names QueueArn --query Attributes.QueueArn --output text)"
   ```
   Console: SQS → `beacon-results-dlq` → **Start DLQ redrive**.
   Redrive is **safe**: results already applied are recognised as duplicates and skipped (ADR 0011).
3. Watch the DLQ go back to 0; the alarm returns to OK.

## Escalate
Always write an RCA: a DLQ message means data was delayed or lost.
