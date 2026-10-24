# Runbook: beacon-probe-errors

**Fires when:** the probe Lambda (`beacon-probe`) reports `Errors ≥ 1` in 3 of the last 5 minutes.

## What it means
The probe crashed instead of finishing its run. A failed *check* (a product returning 502) is **not** an error; that is normal data. An error means the probe itself could not read the snapshot, run, or send its SQS message.

## User impact
For every failed run, that minute has no data: statuses go stale, and **a product could go down without an alert**. With one region, that is a full monitoring outage.

## How to check
1. **Was there a deploy?** Check GitHub Actions for a recent run. Errors starting right after one point at the deploy.
2. **Read the error:**
   ```bash
   aws logs tail /aws/lambda/beacon-probe --since 15m --filter-pattern '?ERROR ?Traceback ?"Task timed out"'
   ```
   Console: CloudWatch → Log groups → `/aws/lambda/beacon-probe`.
3. **Match it to a cause:**

   | Log shows | Likely cause |
   |---|---|
   | `ImportModuleError` / `No module named …` | Bad package (wrong architecture or missing dependency). CI's "Lambda zips import" job should have caught it. |
   | `AccessDenied` on `dynamodb:GetItem` / `sqs:SendMessage` | IAM policy changed, or the queue/table was recreated with a new ARN. |
   | `Task timed out after 50.00 seconds` | Too many slow checks for the 45 s budget. |
   | `ResourceNotFoundException` | Table or queue missing in the home region. |

4. **Is the snapshot there?**
   ```bash
   aws dynamodb get-item --table-name beacon --key '{"PK":{"S":"CONFIG"},"SK":{"S":"MONITORS"}}' --query 'Item.version'
   ```

## How to fix
- **Bad deploy:** `git revert` it, push, and approve the run.
- **IAM / missing resource:** re-run the deploy (Terraform restores the policy or resource). Check `infra/modules/probe/main.tf` if a change was intended.
- **Timeouts:** set slow products to `intervalMin = 5`, lower their `timeoutMs`, or keep fewer products on 1-minute checks.

## Escalate
If it isn't fixed within **15 minutes**, open your important products in a browser yourself: Beacon is blind until this is fixed. Write an RCA.
