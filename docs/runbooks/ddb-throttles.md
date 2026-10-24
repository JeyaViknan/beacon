# Runbook: beacon-ddb-throttles

**Fires when:** the `beacon` table's `ReadThrottleEvents + WriteThrottleEvents` is **≥ 1** in 5 minutes.

## What it means
Requests exceeded the **provisioned capacity** (table 15 RCU / 15 WCU, GSI1 5 / 5), and burst credit ran out. The free tier allows 25 / 25 in total (ADR 0003).

## User impact
Slower or failed writes and reads. The processor retries, which shows as queue age. The API may return errors.

## How to check
1. Dashboard **beacon-ops** → *DynamoDB capacity*: consumed vs provisioned.
2. Which side?
   ```bash
   aws dynamodb describe-table --table-name beacon --query 'Table.[ProvisionedThroughput,GlobalSecondaryIndexes[].ProvisionedThroughput]'
   ```
3. Recent change: more products, more regions, or 1-minute checks on many products. Each product at 1-minute checks costs about 0.25 WCU/s (ADR 0011).

## How to fix
- **Short burst** (e.g. a DLQ redrive): let it pass. Retries are idempotent.
- **Sustained:**
  1. Move some products to `intervalMin = 5`.
  2. Or rebalance capacity inside the free tier in `infra/main/dynamodb.tf` (e.g. table WCU 20, GSI 5; the total must stay ≤ 25) and deploy.
  3. **Never** switch to on-demand without checking cost: it isn't covered by the always-free tier.

## Escalate
If the free-tier limits can't fit the load, stop and decide whether paying is acceptable (HANDOVER §6).
