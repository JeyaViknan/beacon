# ADR 0007 — API as a Lambda Function URL behind CloudFront with an origin-verify header

**Status:** accepted · **Date:** 2026-10-23

**Context.** API Gateway is not always-free. The PWA should call the API on the same origin, to avoid CORS and to share CloudFront's security headers.

**Decision.** A Lambda Function URL (auth `NONE`) serves as a CloudFront origin under `/api/*`, with caching disabled and all viewer headers except `Host` forwarded. CloudFront adds a secret `X-Beacon-Origin` header (a Terraform `random_password`), and the API rejects any request without it, using a constant-time comparison. Every route except health and login also needs a JWT.

**Alternatives.** CloudFront OAC with `AWS_IAM` Function URLs: stronger, but POST/PUT bodies then need the client to send a SHA-256 payload hash, which complicates the PWA. API Gateway: costs money after the first year.

**Consequences.** The Function URL is public, but useless without the header. Since October 2025, public Function URLs need both `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` (restricted with `lambda:InvokedViaFunctionUrl`) in the resource policy (ADR 0012).
