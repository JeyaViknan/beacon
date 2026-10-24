# Runbook: beacon-probe-not-running

**Fires when:** `beacon-probe` had **fewer than 1 invocation in 5 minutes**. Missing data counts as breaching, so silence fires the alarm too.

## What it means
Nothing is invoking the probe. The EventBridge Scheduler schedule is disabled or deleted, the scheduler can't invoke the function, or Lambda is throttling it.

## User impact
**No product is being checked.** No DOWN alerts can fire. The healthchecks.io dead-man's switch fires about 5 minutes later, because the processor gets no messages to ping about.

## How to check
1. **Schedule state:**
   ```bash
   aws scheduler get-schedule --name beacon-probe-every-minute --query '[State,ScheduleExpression]'
   ```
   Console: Amazon EventBridge → Scheduler → Schedules → `beacon-probe-every-minute`. It should be `ENABLED`, `rate(1 minute)`.
2. **Function exists and is Active:**
   ```bash
   aws lambda get-function-configuration --function-name beacon-probe --query '[State,LastUpdateStatus]'
   ```
3. **Throttling:** Lambda → beacon-probe → Monitor → *Throttles*. New accounts can have a low concurrency quota (Service Quotas → Lambda → *Concurrent executions*).
4. **Scheduler can't invoke:** CloudTrail → Event history, filter *Event source* `scheduler.amazonaws.com`, look for `AccessDenied`.

## How to fix
- **Schedule disabled:** `aws scheduler update-schedule …` is fiddly. Re-run the deploy instead: Terraform sets it back to `ENABLED` with the right target and role.
- **Function or role missing:** re-run the deploy.
- **Throttled:** check what else is using concurrency. Request a concurrency quota increase if the account limit is 10.

## Escalate
Treat this as a full monitoring outage from minute 5. Check key products by hand until the probe runs again.
