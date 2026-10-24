# Runbooks

One page per alarm (HANDOVER §15). Every alarm notifies `beacon-ops-alerts` (email + PagerDuty "Beacon Platform") on **ALARM** and again on **OK**, and its description links to the page here.

| Alarm | Page | First question to answer |
|---|---|---|
| `beacon-probe-errors` | [probe-errors](probe-errors.md) | Did a deploy just break the probe? |
| `beacon-probe-not-running` | [probe-not-running](probe-not-running.md) | Is the 1-minute schedule enabled? |
| `beacon-processor-errors` | [processor-errors](processor-errors.md) | Transient (throttle/conflict) or a code bug? |
| `beacon-results-queue-age` | [results-queue-age](results-queue-age.md) | Is the processor's SQS trigger enabled? |
| `beacon-dlq-not-empty` | [dlq-not-empty](dlq-not-empty.md) | What is in the poison message? |
| `beacon-notifier-errors` | [notifier-errors](notifier-errors.md) | Push, PagerDuty, or configuration? |
| `beacon-api-errors` | [api-errors](api-errors.md) | Did a deploy just break the API? |
| `beacon-ddb-throttles` | [ddb-throttles](ddb-throttles.md) | Burst or sustained over capacity? |
| `beacon-processor-duration` | [processor-duration](processor-duration.md) | Which call is slow (X-Ray)? |
| healthchecks.io "beacon-processor" DOWN | [dead-mans-switch](dead-mans-switch.md) | Is anything in the pipeline running at all? |
| A product DOWN alert | [product-down](product-down.md) | Is it really down, and for whom? |

## Before you start

```bash
aws login --profile beacon --region ap-south-1   # browser sign-in, short-lived credentials
export AWS_PROFILE=beacon AWS_REGION=ap-south-1
```

- **Console:** region **Asia Pacific (Mumbai) ap-south-1**. CloudWatch → Dashboards → **beacon-ops** shows every function, the queue, the DLQ and DynamoDB capacity on one page.
- **Logs:** CloudWatch → Log groups → `/aws/lambda/beacon-<function>`. Kept 7 days.
- **Recent deploys:** https://github.com/JeyaViknan/beacon/actions. A red alarm right after a deploy is the deploy until proven otherwise.
- **Rollback:** `git revert <bad commit> && git push`, then approve the run. The pipeline redeploys the previous code.
- After the incident, write an RCA from [`docs/incidents/TEMPLATE.md`](../incidents/TEMPLATE.md).
