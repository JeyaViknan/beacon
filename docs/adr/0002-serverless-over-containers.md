# ADR 0002 — Serverless instead of containers

**Status:** accepted · **Date:** 2026-10-23

**Context.** Hard requirement: AWS free tier only (HANDOVER §6). Load is tiny and spiky: one probe run per minute plus a handful of API calls.

**Decision.** Lambda (Python 3.12, arm64), DynamoDB, SQS, SNS, EventBridge Scheduler, S3 and CloudFront.

**Why.** All are always-free at this scale. ALB, Fargate, NAT Gateway, RDS and EC2 are either not free or only free for 12 months, and they bill per hour even when idle. arm64 Lambda is ~20% cheaper per GB-second than x86.

**Consequences.** No servers to patch, scale-to-zero, and pay-per-use. The trade-offs are cold starts (acceptable for a personal tool), 15-minute max runtimes (irrelevant here), and per-service limits to respect, such as the 10 free CloudWatch alarm metrics.
