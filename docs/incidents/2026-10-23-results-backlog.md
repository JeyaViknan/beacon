# RCA: Probe results piled up for 2 hours during the first deploy

| | |
|---|---|
| **Date** | 2026-10-23 |
| **Severity** | SEV3: no user impact (no products were monitored yet). The same failure in production would be SEV1 (Beacon blind for 2 hours). |
| **Duration** | 19:43 → 21:49 IST (2 h 6 m of stranded results) |
| **Detected by** | CloudWatch alarm `beacon-results-queue-age`, by email |
| **Author** | Jeya Viknan |
| **Status** | reviewed; action items 1–4 done, 5–6 open |

## Summary
During the very first deploy, Terraform created the probe and its 1-minute schedule, but not the processor's SQS trigger, so probe results queued with nothing consuming them. `beacon-results-queue-age` fired 7 minutes after the first stranded message. The deploy then aborted on a network blip; after recovering Terraform state and switching Lambda packaging to S3, the trigger was created and the 122-message backlog drained in 3 minutes. No data was lost and nothing reached the dead-letter queue.

## Impact
- **Users:** none. Beacon was not live, and no products were configured, so every message was an empty heartbeat.
- **Data:** none lost. The 122 queued messages were all processed after recovery (0 processor errors, DLQ max 0).
- **If this happened in production:** 2 hours with no status updates and no DOWN alerts, a full monitoring outage.

## Timeline (IST)
| Time | Event | Evidence |
|---|---|---|
| 18:58 | First apply creates the alarms; `results-queue-age` OK | alarm history |
| 19:32 | Second apply starts (Lambda code now via S3 for most functions) | state lock `Created 14:02:33Z` |
| 19:42 | Probe schedule `beacon-probe-every-minute` created | `scheduler get-schedule` CreationDate |
| 19:43 | First probe invocation; its message reaches the queue at 19:44 | Lambda `Invocations`, SQS `NumberOfMessagesSent` |
| 19:44–21:44 | Queue grows by exactly 1 message a minute, 0 deleted | SQS metrics |
| **19:50** | **`beacon-results-queue-age` → ALARM; email received** (datapoints 188 / 250 / 307 s) | alarm history, email |
| ~20:53 | Second apply aborts: a DNS lookup of the AWS sign-in endpoint fails while refreshing short-lived CLI credentials; Terraform can't save state to S3, writes `errored.tfstate` locally, and leaves the lock held | Terraform output |
| after 20:53 | Diagnosis: queue depth climbing, DLQ empty, no processor trigger exists | `list-event-source-mappings` (empty) |
| — | Recovery: stale lock released (`force-unlock`), local state pushed to S3 (serial 13 → 14), re-planned | Terraform |
| 21:46 | Third apply creates the processor and its SQS trigger; 19 invocations drain the backlog | ESM `LastModified`, Lambda metrics |
| **21:49** | **Queue empty** | SQS metrics |
| 21:50 | Alarm → OK | alarm history |

## Root cause (5 Whys)
1. **Why** did results sit in the queue for 2 hours? The processor's SQS trigger did not exist while the probe was already sending one message a minute.
2. **Why** was the probe running without its consumer? Terraform creates independent resources in parallel. Nothing declared that the probe (producer) needs the trigger (consumer), so the probe and schedule were created first while the processor was still being created.
3. **Why** was the processor not created in that apply? Its creation sent the zip inline in `CreateFunction`. On a brand-new account the first attempts fail while IAM roles propagate, and each retry re-sent the whole zip over a ~1.6 Mbps uplink. Then a DNS blip broke the CLI's credential refresh and aborted the apply mid-way.
4. **Why** did the half-applied state last an hour? Recovery needed manual work: releasing the lock, pushing the locally saved state, and changing how code is packaged before retrying.
5. **Why** was the deploy that fragile? **The first deploy ran from a laptop on a slow, flaky connection, and the design had no ordering guardrail between producer and consumer.** ← root cause

## Detection
- **Time to detect: 7 minutes** after the first stranded message (19:43 → 19:50). That's the designed minimum: age > 180 s for 3 consecutive minutes.
- A **symptom** alarm (queue age) caught a failure that produced **no errors at all**: the consumer simply didn't exist. No error-based alarm could have fired.
- The healthchecks.io dead-man's switch wasn't configured yet; it would have fired too.

## Resolution
1. Confirmed no processor errors and an empty DLQ, so nothing was being lost, only delayed.
2. Released the stale lock and pushed `errored.tfstate` to S3 after checking it was newer (serial 13 vs 12) and that no Terraform process was running.
3. Switched Lambda packaging to an S3 artifacts bucket (ADR 0013), so retries no longer re-upload zips.
4. Re-applied with exported credentials that don't need refreshing mid-run. The trigger was created at 21:46 and the backlog was gone by 21:49.

**Time to recover from detection: 1 h 59 m.** Almost all of it was getting a deploy to complete, not diagnosis.

## What went well
- The alarm fired exactly as designed, and its email told us where to look.
- Idempotent, durable processing (SQS retention 4 days, DLQ, ADR 0011): nothing was lost even after 2 hours.
- Terraform's local `errored.tfstate` fallback meant no state was lost.

## What went badly
- The first deploy came from a laptop on a slow, unreliable network.
- No dependency between producer and consumer in Terraform.
- During recovery, a command printed the temporary root credentials into a session transcript. They expired at 21:50 IST, but it shouldn't have happened, and the CLI is signed in as **root**.

## Where we got lucky
- No products existed yet, so a real 2-hour monitoring outage was only a rehearsal.

## Action items
| # | Action | Type | Owner | Status |
|---|---|---|---|---|
| 1 | Ship Lambda code through an S3 artifacts bucket (ADR 0013) | prevent | Jeya | done |
| 2 | Each probe's schedule waits for the processor's SQS trigger (`consumer_ready` via `terraform_data` in `infra/modules/probe`): a producer never starts before its consumer | prevent | Jeya | done |
| 3 | Deploy from GitHub Actions (stable network, OIDC, plan + apply of the same plan), not a laptop | prevent | Jeya | done (pipeline live; first CI deploy pending CloudFront verification) |
| 4 | Runbook for `results-queue-age` that checks the trigger first | mitigate | Jeya | done |
| 5 | Set up the healthchecks.io dead-man's switch (`docs/setup/alerting.md`) | detect | Jeya | open |
| 6 | Use an admin IAM user with MFA for the CLI instead of root; never print `export-credentials` output | prevent | Jeya | open |

## Evidence
```bash
aws cloudwatch describe-alarm-history --alarm-name beacon-results-queue-age --history-item-type StateUpdate
aws lambda list-event-source-mappings --function-name beacon-processor
aws cloudwatch get-metric-statistics --namespace AWS/SQS --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=beacon-results --start-time 2026-10-23T14:00:00Z --end-time 2026-10-23T16:30:00Z \
  --period 60 --statistics Maximum
```
