# ADR 0011 — Processor idempotency (one transaction per result) and alert delivery semantics

**Status:** accepted · **Date:** 2026-10-23

## Context
SQS standard queues deliver **at least once**, and Lambda retries a whole record when any part of it fails. A naive processor would double-count uptime, append duplicate checks, or open two incidents for one outage. With multiple probe regions, two processor invocations can also update the same product at the same time.

## Decision
Two independent guards:
1. **State machine:** a result that is not newer than the region's last stored result is a `duplicate` and writes nothing.
2. **DynamoDB:** each result is applied with a single `TransactWriteItems`:
   - `Put` raw check `CHECK#<runAt>#<region>` **if not exists**: the idempotency key (product, region, runAt);
   - `Update` product live state **if `version` = what we read** (optimistic locking), `version += 1`;
   - `Update ADD` the R5 / RH / RD rollups;
   - `Put` a new incident (if not exists) or `Update` the open one to RESOLVED.
   All or nothing. If the raw check already exists the whole transaction is cancelled → `DuplicateError` → skip. If the version moved → `ConflictError` → re-read and re-evaluate (up to 3 times).
`latMax` is raised afterwards with a conditional `SET` (DynamoDB has no atomic MAX); it is idempotent by nature.

**Alerts are published after the commit.** If SNS publish fails, it is logged and counted (`NotificationsFailed`) but the record is not failed: a redelivery would be a duplicate anyway. SNS publish is retried by the SDK. In the notifier, PagerDuty failures and "every device failed" raise, so Lambda retries and the `notifier-errors` alarm fires; partial push failures do not, so devices that already received an alert are not notified twice.

## Consequences
- Exactly-once state changes; at-most-once alert publish (with SDK retries), which is the trade-off for never sending duplicate pages. PagerDuty also de-duplicates by `dedup_key` = incident ULID, and iOS replaces notifications with the same `tag`.
- Transactions cost 2 WCU per item. Capacity math at 1-minute checks: ~6 items × 2 WCU + 3 conditional `latMax` writes ≈ 15 WCU per product-minute ≈ 0.25 WCU/s per product, so the 15 WCU table supports ~50–60 products on the free tier.
- `boto3`'s resource client serialises Python values itself: transaction items are passed as native values, not `{"S": ...}` wire format (a test caught this).
