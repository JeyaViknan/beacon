# ADR 0008 — SSM Parameter Store instead of Secrets Manager

**Status:** accepted · **Date:** 2026-10-23

**Decision.** Secrets live in SSM Parameter Store, standard tier, as `SecureString` encrypted with the AWS-managed `aws/ssm` key. Terraform creates placeholders and ignores later value changes. Jeya sets the real values with `scripts/put_secrets.sh`. Lambdas read them at runtime and cache them for 5 minutes.

**Why.** The standard tier is free; Secrets Manager costs $0.40 per secret per month, and a customer-managed KMS key costs $1 per month. Secrets never appear in Git, Terraform variables or GitHub, and the plaintext admin password never leaves Jeya's terminal (only its argon2id hash is stored).

**Consequences.** No automatic rotation. Rotating means re-running `put_secrets.sh`; a new JWT secret signs everyone out, which is fine for a single user.
