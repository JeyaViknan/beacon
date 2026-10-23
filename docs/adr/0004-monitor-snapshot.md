# ADR 0004 — Monitor snapshot item for probes

**Status:** accepted · **Date:** 2026-10-23

**Context.** Probes run every minute, possibly in several regions. Reading every product on every run costs read capacity that grows with the number of products, and it couples the data plane to the shape of the product records.

**Decision.** The API (control plane) rebuilds one compact `CONFIG/MONITORS` item whenever products change. Probes (data plane) read only that item, cached for 30 s per container.

**Why.** A probe run costs one `GetItem`, no matter how many products exist. Probes see only the fields they need. Adding, pausing or deleting a product takes effect within about a minute without a redeploy. The snapshot merges the just-written product explicitly, because the GSI used to list products is eventually consistent.

**Consequences.** There is up to ~30 s of staleness after an edit, which is acceptable for 1-minute checks.
