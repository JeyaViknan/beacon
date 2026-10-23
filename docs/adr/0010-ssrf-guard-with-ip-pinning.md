# ADR 0010 — SSRF guard with DNS resolution and IP pinning

**Status:** accepted · **Date:** 2026-10-23

## Context
Beacon fetches URLs a user typed, from inside AWS. A malicious or mistaken URL could point at internal endpoints. In Lambda the obvious target is the **runtime API on 127.0.0.1:9001** (it hands out invocation events); on other compute it is the **instance metadata service at 169.254.169.254** (temporary IAM credentials). Hostnames can hide these (`localhost`, `2130706433`, `0x7f000001`, IPv4-mapped IPv6, 6to4, Teredo), and DNS can change between "check" and "connect" (DNS rebinding).

## Decision
1. Allow only `http`/`https`, no credentials in the URL.
2. Resolve DNS ourselves and reject the host if **any** resolved address is non-public (private, loopback, link-local, CGNAT, multicast, reserved, ULA, and IPv6 forms that embed IPv4).
3. **Pin**: connect to the IP we checked, and send the real hostname as `Host` and TLS SNI (`sni_hostname`), so the certificate is still verified for the hostname. There is no second DNS lookup to rebind.
4. Follow redirects manually, max 3, each hop through steps 1–3.
5. Disable keep-alive for checks so a TLS connection opened for one hostname is never reused for another hostname on the same IP.
6. Read at most 1 MB of body; send `User-Agent: BeaconProbe/1.0 (+uptime monitor)`.
7. The API applies the same rules when a product is created or updated.

## Consequences
- Every new connection pays full TCP + TLS setup. For uptime checks that is a feature: latency includes what a new visitor pays.
- Products on IPv6-only hosts cannot be checked from Lambda outside a VPC (no IPv6 egress); IPv4 is preferred when both exist.
- Tests cover every blocked range, the encoding tricks, rebinding-style multi-record answers, redirect hops and the pinning headers.
