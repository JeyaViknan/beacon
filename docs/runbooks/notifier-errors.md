# Runbook: beacon-notifier-errors

**Fires when:** `beacon-notifier` reports `Errors ≥ 1` in 5 minutes.

## What it means
An alert reached SNS, but the notifier couldn't deliver it. It raises only when **PagerDuty fails** or **every push device fails**; partial push failures are just counted. Lambda retries twice, so one error can be followed by a success.

## User impact
**Phone push or PagerDuty pages may be missing.** Email is unaffected: it comes from SNS directly.

## How to check
```bash
aws logs tail /aws/lambda/beacon-notifier --since 30m
```

| Log shows | Likely cause | Fix |
|---|---|---|
| `PagerDuty returned HTTP 400` | Wrong or deleted routing key | Re-enter it: `make secrets` (PagerDuty routing key) |
| `PagerDuty unreachable` | Network / PagerDuty outage | Check status.pagerduty.com; retries usually recover |
| `all push deliveries failed`, status 403 | VAPID key pair mismatch (web build public key ≠ SSM private key) | Rebuild the web app with the matching `VITE_VAPID_PUBLIC_KEY`, then re-enable notifications on the phone |
| `Push failed` 404/410 | Phone unsubscribed; removed automatically | Settings → Enable notifications on the phone |
| `Web Push not configured` | VAPID secret missing | `make secrets` |

## How to fix
Use the table above, then send **Settings → Send test notification** from the app and confirm push + email arrive.

## Escalate
If DOWN alerts reach you only by email for more than an hour, check product status in the app manually.
