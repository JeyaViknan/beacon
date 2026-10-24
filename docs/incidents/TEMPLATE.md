# RCA: <short title>

> Copy to `docs/incidents/YYYY-MM-DD-<slug>.md`. Blameless: describe systems and decisions, not people.
> Times in **IST** (UTC+5:30). Keep it to facts you can point at: alarm history, logs, metrics, commits.

| | |
|---|---|
| **Date** | YYYY-MM-DD |
| **Severity** | SEV1 (Beacon blind / customer-facing outage) · SEV2 (degraded, delayed alerts) · SEV3 (no user impact) |
| **Duration** | start → end (total) |
| **Detected by** | alarm name / healthchecks.io / a person |
| **Author** | |
| **Status** | draft · reviewed · action items done |

## Summary
Two or three sentences: what broke, for how long, the impact, and how it was fixed.

## Impact
- Who or what was affected (products not monitored, alerts delayed, app unavailable…).
- Data impact (lost or late results, uptime gaps).
- What did **not** break.

## Timeline (IST)
| Time | Event |
|---|---|
| HH:MM | Trigger: the change or event that started it |
| HH:MM | First symptom |
| HH:MM | Detection: alarm fired / page received |
| HH:MM | Acknowledged |
| HH:MM | Mitigation applied |
| HH:MM | Recovered (metrics normal, alarm OK) |

## Root cause (5 Whys)
1. **Why** did <the symptom> happen? Because …
2. **Why** …? Because …
3. **Why** …? Because …
4. **Why** …? Because …
5. **Why** …? Because … ← the root cause, usually a missing guardrail, not a person.

## Detection
- How was it detected, and how long after it started (**time to detect**)?
- Did the right alarm fire? Was anything noisy or missing?

## Resolution
- What was done, in order, and **time to recover** from detection.
- Commands, commits or console actions (link them).

## What went well
-

## What went badly
-

## Where we got lucky
-

## Action items
| # | Action | Type (prevent / detect / mitigate) | Owner | Due | Status |
|---|---|---|---|---|---|
| 1 | | | | | |

## Evidence
Links: alarm history, dashboards, logs queries, commits, PRs.
