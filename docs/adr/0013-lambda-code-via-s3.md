# ADR 0013 — Deploy Lambda code through an S3 artifacts bucket

**Status:** accepted · **Date:** 2026-10-23

## Context
The first `terraform apply` sent each zip inline in `CreateFunction` (`filename = …`). On a brand-new account, AWS rejects the first `CreateFunction` attempts for a few minutes while new IAM roles propagate, and the provider retries by re-sending the whole zip every time. Over a ~1.6 Mbps uplink, a 5 MB function took 7–10 minutes, the 13 MB notifier never finished, and the processor failed with HTTP 408. A plain S3 upload of the same 4.6 MB zip took 23 s.

## Decision
- A private `beacon-artifacts-<account>` bucket (SSE-S3, public access blocked, bucket-owner-enforced).
- `aws_s3_object.lambda[fn]` uploads `dist/<fn>.zip` to `lambda/<fn>.zip`. It re-uploads only when the zip's MD5 changes, and the zips are deterministic, so that only happens when the code actually changed.
- Every home-region Lambda, including the Mumbai probe, uses `s3_bucket`/`s3_key`, plus `source_code_hash`, so the function updates only when the code changes.
- Remote-region probes keep inline upload, because Lambda reads code only from a bucket in its own region. Each extra region would otherwise need its own bucket.

## Consequences
- Retries during role propagation cost nothing: Lambda fetches from S3 inside AWS.
- The same path suits CI (GitHub runners upload once).
- The deploy role can read and write `beacon-artifacts-*`.
- Storage is a few tens of MB, well inside the free tier.
