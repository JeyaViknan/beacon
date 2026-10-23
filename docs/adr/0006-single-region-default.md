# ADR 0006 — Single probe region by default, multi-region opt-in

**Status:** accepted · **Date:** 2026-10-23

**Decision.** `probe_regions = ["ap-south-1"]` by default. `ap-southeast-1` and `us-east-1` can be switched on in Terraform. Each region has a fixed provider alias, and its probe module is enabled with `count`, because Terraform cannot create providers in a `for_each`.

**Why.** One region costs nothing extra. Extra regions add cross-region SQS and DynamoDB traffic (a few paise per month) and make the quorum logic matter (ADR 0005). Most of Jeya's users are in India, so Mumbai is the right single vantage point.

**Consequences.** With one region, a network problem between Mumbai and a product looks like an outage. Turning on a second region makes the quorum ignore single-region blips.
