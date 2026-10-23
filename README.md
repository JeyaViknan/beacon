# Beacon

A personal uptime and incident monitor for every live product I run, with an installable iPhone app (PWA) and push alerts.
It checks each product every minute, opens an incident after consecutive failures, alerts the phone (Web Push), email and PagerDuty, and shows uptime, latency and incident history.

Runs entirely on AWS serverless inside the free tier: Lambda, DynamoDB, SQS, SNS, EventBridge Scheduler, S3 and CloudFront, all managed with Terraform and deployed by GitHub Actions over OIDC.

> Work in progress. `HANDOVER.md` is the full specification; `docs/` holds ADRs, runbooks and RCAs.

## Local development

```bash
make setup    # Python 3.12 venv + dev dependencies (needs uv)
make lint test
make web      # frontend typecheck, lint, test, build
```
