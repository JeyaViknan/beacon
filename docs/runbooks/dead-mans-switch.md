# Runbook: healthchecks.io "beacon-processor" is DOWN

**Fires when:** healthchecks.io hasn't received a ping for **more than 5 minutes** (period 1 min + grace 5 min). It alerts you directly, outside AWS.

## What it means
The processor hasn't completed a clean batch for at least 5 minutes. Anything from the schedule to the processor may be broken, **including AWS itself**, which is why this check lives outside AWS (ADR 0009).

## User impact
Treat it as **Beacon is blind**: product outages may go unnoticed.

## How to check
1. Did CloudWatch alarm too? `beacon-probe-not-running`, `beacon-results-queue-age`, `beacon-processor-errors`: follow whichever fired.
2. **None fired?** Then either:
   - **AWS is having an issue:** check https://health.aws.amazon.com/health/status for ap-south-1.
   - **Only the ping is broken:** look for `healthchecks.io ping failed` in processor logs, or a changed ping URL:
     ```bash
     aws logs tail /aws/lambda/beacon-processor --since 15m --filter-pattern '"healthchecks.io ping failed"'
     ```
3. Is the probe running at all? Lambda → beacon-probe → Monitor → Invocations.

## How to fix
- Follow the CloudWatch runbook that matches.
- Wrong ping URL: `make secrets` (healthchecks.io ping URL). The processor picks it up within 5 minutes.
- AWS outage: nothing to fix in Beacon; check key products by hand until it recovers.

## Escalate
Always write an RCA if this fired without a planned change.
