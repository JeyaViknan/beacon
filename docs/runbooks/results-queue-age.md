# Runbook: beacon-results-queue-age

**Fires when:** the oldest message in `beacon-results` is **older than 180 s** for 3 consecutive minutes.

## What it means
Probe results are arriving but not being consumed fast enough, or not at all.

## User impact
Every minute the queue grows is a minute of **detection delay**: a product can be down without an alert yet. Nothing is lost: messages are kept 4 days.

## How to check
1. **Is the processor's trigger there and enabled?** This was the cause on 2026-10-23.
   ```bash
   aws lambda list-event-source-mappings --function-name beacon-processor --query 'EventSourceMappings[].[UUID,State,LastProcessingResult]'
   ```
   Nothing listed = the trigger doesn't exist. `Disabled` = it was switched off.
2. **Queue depth:**
   ```bash
   aws sqs get-queue-attributes --queue-url "$(aws sqs get-queue-url --queue-name beacon-results --query QueueUrl --output text)" --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
   ```
   Many *NotVisible* = the processor is receiving but failing or slow.
3. **Is the processor erroring or throttled?** See [processor-errors](processor-errors.md); the dashboard shows Errors and Duration.

## How to fix
- **Trigger missing:** re-run the deploy; Terraform recreates `aws_lambda_event_source_mapping.processor`.
- **Trigger disabled:** `aws lambda update-event-source-mapping --uuid <UUID> --enabled`.
- **Processor failing:** fix that first; the backlog drains on its own (up to 2 concurrent batches of 10).

## Escalate
Older than 10 minutes and growing, with no obvious cause, means you write an RCA. Use [`2026-10-23-results-backlog.md`](../incidents/2026-10-23-results-backlog.md) as a worked example.
