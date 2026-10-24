# ADR 0014 — CI/CD: GitHub Actions, OIDC, an approval gate and pinned actions

**Status:** accepted · **Date:** 2026-10-23

## Context
Deploys must be repeatable, reviewed and keyless. GitHub must not hold AWS secrets (HANDOVER §12). A broken build must never reach AWS.

## Decision
- **`ci.yml`** runs on pull requests and branch pushes, and is *called* by `deploy.yml` (`workflow_call`), so the deploy always runs the full CI first. It has four parallel jobs:
  - Python lint + tests (85% coverage gate).
  - Web typecheck/lint/test/build.
  - Terraform fmt + validate on every stack.
  - Lambda packages: build the arm64 zips and import every handler inside `public.ecr.aws/lambda/python:3.12-arm64` (QEMU), catching wrong-architecture wheels before AWS sees them.
- **`deploy.yml`** runs on push to `main` (or manually):
  1. CI.
  2. The job targets the GitHub environment **`production`**, which requires Jeya's approval.
  3. OIDC → `beacon-github-deploy`. The role trusts only `repo:JeyaViknan@157094732/beacon@1431377621:environment:production`: GitHub's *immutable* subject, which pins the owner and repo by numeric ID, so a deleted-and-recreated repo with the same name can never assume the role.
  4. Build the zips, then `terraform plan -out` (summary in the job page) and `terraform apply` of that exact plan.
  5. Publish the PWA (S3 sync + CloudFront invalidation).
  6. Smoke test: `/api/health` must report the **commit being deployed**, and `/` must return the app.
- **Least privilege for the deploy role:** service actions only on `beacon-*` ARNs, plus an explicit deny on changing its own IAM. Verified with the IAM policy simulator.
- **Supply chain:** every action is pinned to a full commit SHA (release tag in a comment), so a moved or hijacked tag can't change what runs.
- **No injection:** workflow expressions reach shell scripts only through `env:`, never inlined.
- **Serialised deploys:** `concurrency: deploy-production` with `cancel-in-progress: false`, so an apply is never interrupted midway.
- **Repo visibility:** public. Required-reviewer protection is free on public repos. The only sensitive value, the alert email, is a GitHub *secret* (masked in logs). Everything else is an ID, not a credential.

## Lesson from the first run
The first deploy failed at the OIDC step with `Not authorized to perform sts:AssumeRoleWithWebIdentity`. The trust policy expected the classic name-based subject (`repo:JeyaViknan/beacon:…`), but the repo uses GitHub's immutable subject format (`gh api repos/JeyaViknan/beacon/actions/oidc/customization/sub` shows `use_immutable_subject: true`). CloudTrail's failed `AssumeRoleWithWebIdentity` events show the exact subject that was presented, which made the fix a one-line, verifiable change (`github_oidc_sub_prefix` in `infra/bootstrap`).

## Consequences
- Jeya approves before the plan is visible; the plan lands in the job summary for audit. A stricter split (a separate plan job with its own role and environment, then an apply job) is a later improvement.
- The deploy is all-or-nothing per commit. Rollback = `git revert` + approve the new run (drill 2 in HANDOVER §18).
