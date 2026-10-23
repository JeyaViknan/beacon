# ADR 0005 — Quorum and consecutive thresholds before alerting

**Status:** accepted · **Date:** 2026-10-23

## Context
A single failed HTTP check is usually noise: a dropped packet, a cold start, a probe-side DNS hiccup. Paging on every blip trains the on-call (Jeya) to ignore alerts. With more than one probe region, one region can also be the broken party.

## Decision
- A product is **failing** for an evaluation when failing *fresh* regions ≥ quorum. Default quorum = ceil(fresh / 2); a configured quorum is capped at the number of fresh regions, so a product is never unmonitorable when regions go quiet.
- A region is **fresh** while its latest result is younger than 2 × `intervalMin`.
- An incident **opens** after `openAfter` (default 2) consecutive failing evaluations and **resolves** after `resolveAfter` (default 2) consecutive passing ones.
- Counters step **once per minute**. When a second region reports in the same minute, we re-evaluate from the counters saved before that minute's step (`evalBase`), so the verdict can change without double-counting.
- Uptime rollups receive a delta per evaluation, so a minute counts once per product even with three regions; a same-minute verdict flip moves that minute between up and down.
- Incident start = first failing evaluation of the streak; resolution = first passing evaluation of the streak, so "down for 6m 12s" is the real outage, not outage + detection delay.

## Consequences
- Detection delay ≈ `openAfter` minutes (2 by default). The demo target uses `openAfter = 1` for a fast demo.
- On cold start (only one region has reported) a single region decides alone; this is deliberate and covered by a test.
- Everything lives in one pure function (`beacon_core.state_machine.evaluate`), fully table-tested.
