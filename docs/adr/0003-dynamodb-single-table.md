# ADR 0003 — DynamoDB single table, provisioned within 25/25

**Status:** accepted · **Date:** 2026-10-23

**Context.** Access patterns are known up front: get or list products, write checks, increment rollups, list incidents, and store push subscriptions and settings.

**Decision.** One table `beacon` with `PK`/`SK`, one GSI (`GSI1`) for the product list and the incident feed, and TTL on all time-series data. Provisioned capacity: table 15/15 plus GSI 5/5, i.e. 20/20 out of the free 25/25.

**Why.** Single-table design serves each screen with one `Query`. Provisioned capacity inside the always-free allowance costs $0; on-demand has no permanent free tier. TTL deletes are free, which keeps the table small without cleanup jobs.

**Consequences.** Capacity is finite. ADR 0011 has the write-capacity maths (~50 products at 1-minute checks). The `ddb-throttles` alarm tells us when we hit the ceiling.
