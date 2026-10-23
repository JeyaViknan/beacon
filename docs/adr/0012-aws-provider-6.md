# ADR 0012 — AWS Terraform provider 6.x (instead of 5.x)

**Status:** accepted · **Date:** 2026-10-23

**Context.** HANDOVER §13 says `aws ~> 5.x`. Since October 2025, a new public Lambda Function URL needs a second resource-policy statement: `lambda:InvokeFunction` restricted by the `lambda:InvokedViaFunctionUrl` condition. Without it, requests get 403. Provider 5.x (last release 5.100.0) cannot express that condition; 6.x has `aws_lambda_permission.invoked_via_function_url`.

**Decision.** Use `hashicorp/aws ~> 6.0` in every stack (6.70.0 at the time of writing). DynamoDB GSIs use `key_schema` blocks, because `hash_key`/`range_key` inside a GSI are deprecated in 6.x.

**Consequences.** It is a newer major version than the handover assumed. `terraform validate` is clean, and the lock files pin exact versions.
