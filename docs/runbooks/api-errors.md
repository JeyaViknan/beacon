# Runbook: beacon-api-errors

**Fires when:** `beacon-api` reports `Errors ≥ 5` in 5 minutes.

## What it means
Unhandled exceptions or timeouts in the API. Normal 4xx answers (wrong password, validation errors, 404) are **not** Lambda errors; this is 5xx territory.

## User impact
The app shows errors or blank screens. Monitoring itself (probe → processor → alerts) is **not** affected.

## How to check
1. Deploy just happened? Check GitHub Actions.
2. Logs:
   ```bash
   aws logs tail /aws/lambda/beacon-api --since 30m --filter-pattern '?ERROR ?Traceback ?"Task timed out"'
   ```
3. Quick health probe through CloudFront:
   ```bash
   curl -s "$(terraform -chdir=infra/main output -raw cloudfront_url)/api/health"
   ```

| Log shows | Likely cause |
|---|---|
| `ProvisionedThroughputExceededException` | DynamoDB throttling. See [ddb-throttles](ddb-throttles.md). |
| `ParameterNotFound` | An SSM parameter was deleted; re-run the deploy, then `make secrets`. |
| `Task timed out after 20.00 seconds` | Usually *Test now* against a very slow site, or DynamoDB slowness. |

## How to fix
Revert a bad deploy, or fix the dependency named in the logs. Then confirm `/api/health` and log in from the phone.

## Escalate
If it isn't fixed within 30 minutes, write an RCA.
