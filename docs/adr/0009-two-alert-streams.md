# ADR 0009 — Two alert streams plus an external dead-man's switch

**Status:** accepted · **Date:** 2026-10-23

**Decision.**
- `beacon-product-alerts`: products Beacon watches (DOWN, RECOVERED, SLOW, TLS). Delivered by email (SNS filter policy) and by the notifier Lambda (Web Push + PagerDuty).
- `beacon-ops-alerts`: Beacon itself (CloudWatch alarms). Delivered by email and an SNS HTTPS subscription to PagerDuty's CloudWatch integration, with **no Beacon code in the path**.
- healthchecks.io is pinged by the processor after each clean batch. If pings stop for 5 minutes, healthchecks.io alerts Jeya, completely outside AWS.

**Why.** "Who watches the watcher?" If the notifier is broken, ops alarms must still reach a human. If the whole account or region is broken, CloudWatch may not alarm, but the missing heartbeat will.

**Consequences.** Three alerting paths to configure (M7). The PagerDuty ops URL lives in SSM, created by `infra/bootstrap` so `infra/main` can read it at plan time.
