"""One HTTP check for one product (HANDOVER §8.2), shared by the probe and the API's "Test now".

``ok`` is true only when there is no network/DNS/TLS error, the final response arrives within
``timeoutMs``, its status is in ``expectedStatus``, and ``keyword`` (if set) appears in the first
1 MB of the body. Every hop goes through the SSRF guard and connects to the checked IP.
"""

import asyncio
import ssl
import time
from collections.abc import Callable, Iterable
from urllib.parse import urljoin

import httpx

from beacon_core.models import CheckResult, MonitorSpec, status_matches
from beacon_core.ssrf import DNSError, Resolver, SSRFError, resolve_target, system_resolver

USER_AGENT = "BeaconProbe/1.0 (+uptime monitor)"
MAX_BODY_BYTES = 1_048_576
MAX_REDIRECTS = 3
REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})

Clock = Callable[[], float]


class CheckError(Exception):
    """A check-level failure with a short human-readable reason."""


def new_client() -> httpx.AsyncClient:
    """HTTP client for checks.

    - No automatic redirects: each hop must pass the SSRF guard.
    - No keep-alive: we connect to pinned IPs with per-request SNI, and a pooled TLS connection
      for one hostname must never be reused for another hostname on the same IP.
    - ``trust_env=False``: ignore proxy env vars.
    """
    return httpx.AsyncClient(
        follow_redirects=False,
        trust_env=False,
        limits=httpx.Limits(max_keepalive_connections=0, max_connections=50),
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )


def _causes(exc: BaseException) -> Iterable[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def describe_error(exc: BaseException, timeout_ms: int) -> str:
    """Map transport exceptions to the short texts from HANDOVER §8.2."""
    for cause in _causes(exc):
        if isinstance(cause, CheckError | DNSError):
            return str(cause)
        if isinstance(cause, SSRFError):
            return f"Blocked: {cause}"
        if isinstance(cause, TimeoutError | httpx.TimeoutException):
            return f"Timeout after {timeout_ms} ms"
        if isinstance(cause, ssl.SSLCertVerificationError):
            reason = (cause.verify_message or "verification failed").lower()
            if "expired" in reason:
                return "TLS: certificate expired"
            if "hostname" in reason or "ip address mismatch" in reason:
                return "TLS: certificate hostname mismatch"
            if "self-signed" in reason or "self signed" in reason:
                return "TLS: self-signed certificate"
            return f"TLS: {reason}"
        if isinstance(cause, ssl.SSLError):
            return "TLS: handshake failed"
    for cause in _causes(exc):
        if isinstance(cause, ConnectionRefusedError):
            return "Connection refused"
    if isinstance(exc, httpx.ConnectError):
        return "Connection failed"
    if isinstance(exc, httpx.RemoteProtocolError):
        return "Connection closed by server"
    return f"Network error: {type(exc).__name__}"


async def _read_capped(response: httpx.Response, limit: int = MAX_BODY_BYTES) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        chunks.append(chunk)
        size += len(chunk)
        if size >= limit:
            break
    return b"".join(chunks)[:limit]


async def _fetch(
    client: httpx.AsyncClient,
    spec: MonitorSpec,
    resolver: Resolver,
    clock: Clock,
    started: float,
) -> CheckResult:
    url = spec.check_url
    for hop in range(MAX_REDIRECTS + 1):
        target = await resolve_target(url, resolver)
        request = client.build_request(
            spec.method,
            target.pinned_url,
            headers={"Host": target.host_header},
            extensions={"sni_hostname": target.host} if target.scheme == "https" else {},
        )
        response = await client.send(request, stream=True)
        try:
            location = response.headers.get("location")
            if response.status_code in REDIRECT_CODES and location:
                if hop == MAX_REDIRECTS:
                    raise CheckError(f"Too many redirects (>{MAX_REDIRECTS})")
                url = urljoin(target.url, location)
                continue

            latency_ms = round((clock() - started) * 1000)
            code = response.status_code
            if not status_matches(code, spec.expected_status):
                return _result(spec, False, code, latency_ms, f"HTTP {code}")
            if spec.keyword and spec.method == "GET":
                body = (await _read_capped(response)).decode("utf-8", errors="replace")
                if spec.keyword not in body:
                    return _result(
                        spec, False, code, latency_ms, f'Keyword "{spec.keyword}" missing', False
                    )
                return _result(spec, True, code, latency_ms, None, True)
            return _result(spec, True, code, latency_ms, None)
        finally:
            await response.aclose()
    raise CheckError(f"Too many redirects (>{MAX_REDIRECTS})")  # pragma: no cover


def _result(
    spec: MonitorSpec,
    ok: bool,
    code: int | None,
    latency_ms: int | None,
    error: str | None,
    keyword_ok: bool | None = None,
) -> CheckResult:
    return CheckResult(
        product_id=spec.id,
        ok=ok,
        http_code=code,
        latency_ms=latency_ms,
        error=error,
        keyword_ok=keyword_ok,
    )


async def run_check(
    client: httpx.AsyncClient,
    spec: MonitorSpec,
    *,
    resolver: Resolver = system_resolver,
    clock: Clock = time.perf_counter,
) -> CheckResult:
    """Run one check. Never raises for target-side problems: failures become ``ok=False``."""
    started = clock()
    try:
        async with asyncio.timeout(spec.timeout_ms / 1000):
            return await _fetch(client, spec, resolver, clock, started)
    except (TimeoutError, httpx.HTTPError, CheckError, SSRFError, ssl.SSLError, OSError) as exc:
        return _result(spec, False, None, None, describe_error(exc, spec.timeout_ms))


async def run_checks(
    specs: Iterable[MonitorSpec],
    *,
    concurrency: int = 20,
    budget_s: float = 45.0,
    resolver: Resolver = system_resolver,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[CheckResult], list[str]]:
    """Run checks concurrently. Returns (results, ids skipped because the run budget ran out).

    Skipped checks are *not* reported as failures: running out of probe time says nothing about
    the target, so that minute simply has no data for those products.
    """
    semaphore = asyncio.Semaphore(concurrency)
    owned = client is None
    http = client or new_client()

    async def one(spec: MonitorSpec) -> CheckResult:
        async with semaphore:
            return await run_check(http, spec, resolver=resolver)

    try:
        tasks = {asyncio.create_task(one(spec)): spec.id for spec in specs}
        if not tasks:
            return [], []
        done, pending = await asyncio.wait(tasks, timeout=budget_s)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        results = [task.result() for task in done]
        order = {pid: i for i, pid in enumerate(tasks.values())}
        results.sort(key=lambda r: order[r.product_id])
        return results, [tasks[t] for t in pending]
    finally:
        if owned:
            await http.aclose()
