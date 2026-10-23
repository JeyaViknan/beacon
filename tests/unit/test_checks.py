"""HTTP check rules (HANDOVER §8.2) with httpx mocked by respx."""

import asyncio
import ssl

import httpx
import pytest
import respx

from beacon_core.checks import (
    MAX_BODY_BYTES,
    USER_AGENT,
    CheckError,
    describe_error,
    new_client,
    run_check,
    run_checks,
)
from beacon_core.models import MonitorSpec
from beacon_core.ssrf import DNSError, SSRFError

IP = "93.184.216.34"
HOSTS = {"example.com": [IP], "www.example.com": [IP], "evil.example": ["169.254.169.254"]}


async def fake_resolver(host: str, port: int) -> list[str]:
    if host not in HOSTS:
        raise OSError("not found")
    return HOSTS[host]


def spec(**kw) -> MonitorSpec:
    base = {"id": "P1", "check_url": "https://example.com/health"}
    base.update(kw)
    return MonitorSpec.model_validate(base)


def check(s: MonitorSpec):
    async def go():
        async with new_client() as client:
            return await run_check(client, s, resolver=fake_resolver)

    return asyncio.run(go())


@respx.mock
def test_ok_response_pins_ip_and_sends_host_sni_and_user_agent():
    route = respx.get(f"https://{IP}/health").respond(200, text="hello")
    result = check(spec())
    assert result.ok is True
    assert result.http_code == 200
    assert result.error is None
    assert result.latency_ms is not None and result.latency_ms >= 0
    request = route.calls.last.request
    assert request.headers["host"] == "example.com"
    assert request.headers["user-agent"] == USER_AGENT
    assert request.extensions["sni_hostname"] == "example.com"


@pytest.mark.parametrize(
    ("status", "expected", "ok", "error"),
    [
        (200, "200-399", True, None),
        (302, "200-399", True, None),  # a 302 without Location is just a status
        (404, "200-399", False, "HTTP 404"),
        (502, "200-399", False, "HTTP 502"),
        (503, "200-399", False, "HTTP 503"),
        (204, "200", False, "HTTP 204"),
        (401, "200-299,401", True, None),
    ],
)
@respx.mock
def test_status_ranges(status, expected, ok, error):
    respx.get(f"https://{IP}/health").respond(status)
    result = check(spec(expected_status=expected))
    assert (result.ok, result.http_code, result.error) == (ok, status, error)


@respx.mock
def test_keyword_found():
    respx.get(f"https://{IP}/health").respond(200, text="<h1>Welcome back</h1>")
    result = check(spec(keyword="Welcome"))
    assert result.ok is True
    assert result.keyword_ok is True


@respx.mock
def test_keyword_missing():
    respx.get(f"https://{IP}/health").respond(200, text="maintenance mode")
    result = check(spec(keyword="Welcome"))
    assert result.ok is False
    assert result.keyword_ok is False
    assert result.error == 'Keyword "Welcome" missing'


@respx.mock
def test_keyword_after_first_megabyte_is_not_seen():
    respx.get(f"https://{IP}/health").respond(200, content=b"x" * MAX_BODY_BYTES + b"Welcome")
    result = check(spec(keyword="Welcome"))
    assert result.error == 'Keyword "Welcome" missing'


@respx.mock
def test_head_request():
    route = respx.head(f"https://{IP}/health").respond(200)
    assert check(spec(method="HEAD")).ok is True
    assert route.called


@respx.mock
def test_http_url_has_no_sni():
    route = respx.get(f"http://{IP}/").respond(200)
    assert check(spec(check_url="http://example.com/")).ok is True
    assert "sni_hostname" not in route.calls.last.request.extensions


@respx.mock
def test_redirects_are_followed_and_each_hop_rechecked():
    respx.get(f"https://{IP}/health").respond(
        301, headers={"Location": "https://www.example.com/a"}
    )
    respx.get(f"https://{IP}/a").respond(302, headers={"Location": "/b"})
    final = respx.get(f"https://{IP}/b").respond(200)
    result = check(spec())
    assert result.ok is True
    assert final.calls.last.request.headers["host"] == "www.example.com"


@respx.mock
def test_redirect_to_metadata_is_blocked():
    respx.get(f"https://{IP}/health").respond(302, headers={"Location": "http://evil.example/"})
    result = check(spec())
    assert result.ok is False
    assert result.error is not None
    assert result.error.startswith("Blocked: evil.example resolves to a non-public address")


@respx.mock
def test_redirect_to_ip_literal_is_blocked():
    respx.get(f"https://{IP}/health").respond(
        302, headers={"Location": "http://169.254.169.254/latest/meta-data/"}
    )
    assert check(spec()).error.startswith("Blocked:")


@respx.mock
def test_redirect_to_other_scheme_is_blocked():
    respx.get(f"https://{IP}/health").respond(302, headers={"Location": "file:///etc/passwd"})
    assert check(spec()).error == "Blocked: only http:// and https:// URLs are allowed"


@respx.mock
def test_more_than_three_redirects_fail():
    for i in range(5):
        respx.get(f"https://{IP}/r{i}").respond(302, headers={"Location": f"/r{i + 1}"})
    result = check(spec(check_url="https://example.com/r0"))
    assert result.ok is False
    assert result.error == "Too many redirects (>3)"


@respx.mock
def test_exactly_three_redirects_are_fine():
    for i in range(3):
        respx.get(f"https://{IP}/r{i}").respond(302, headers={"Location": f"/r{i + 1}"})
    respx.get(f"https://{IP}/r3").respond(200)
    assert check(spec(check_url="https://example.com/r0")).ok is True


def test_dns_failure():
    result = check(spec(check_url="https://unknown.example/"))
    assert result.ok is False
    assert result.error == "DNS: host not found"


@respx.mock
def test_transport_timeout():
    respx.get(f"https://{IP}/health").mock(side_effect=httpx.ReadTimeout("slow"))
    assert check(spec(timeout_ms=10_000)).error == "Timeout after 10000 ms"


@respx.mock
def test_overall_deadline_covers_slow_responses():
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200)

    respx.get(f"https://{IP}/health").mock(side_effect=slow)
    result = check(spec(timeout_ms=50))
    assert result.ok is False
    assert result.error == "Timeout after 50 ms"


def _tls_error(message: str) -> httpx.ConnectError:
    cause = ssl.SSLCertVerificationError(1, "certificate verify failed")
    cause.verify_message = message
    try:
        raise httpx.ConnectError("tls") from cause
    except httpx.ConnectError as exc:
        return exc


def _chained(outer: Exception, inner: BaseException) -> Exception:
    try:
        raise outer from inner
    except Exception as exc:  # noqa: BLE001 - building a chained exception for the test
        return exc


@pytest.mark.parametrize(
    ("exc", "text"),
    [
        (_tls_error("certificate has expired"), "TLS: certificate expired"),
        (
            _tls_error("Hostname mismatch, certificate is not valid for 'x'."),
            "TLS: certificate hostname mismatch",
        ),
        (_tls_error("self-signed certificate"), "TLS: self-signed certificate"),
        (
            _tls_error("unable to get local issuer certificate"),
            "TLS: unable to get local issuer certificate",
        ),
        (_chained(httpx.ConnectError("x"), ssl.SSLError("bad handshake")), "TLS: handshake failed"),
        (_chained(httpx.ConnectError("x"), ConnectionRefusedError()), "Connection refused"),
        (httpx.ConnectError("unreachable"), "Connection failed"),
        (httpx.RemoteProtocolError("eof"), "Connection closed by server"),
        (httpx.ConnectTimeout("t"), "Timeout after 5000 ms"),
        (TimeoutError(), "Timeout after 5000 ms"),
        (DNSError("DNS: host not found"), "DNS: host not found"),
        (
            SSRFError("x resolves to a non-public address (10.0.0.1)"),
            "Blocked: x resolves to a non-public address (10.0.0.1)",
        ),
        (CheckError("Too many redirects (>3)"), "Too many redirects (>3)"),
        (httpx.DecodingError("bad gzip"), "Network error: DecodingError"),
    ],
)
def test_describe_error(exc, text):
    assert describe_error(exc, 5_000) == text


def test_tls_failure_during_check():
    # respx rewrites exception causes, so use httpx's own MockTransport, which keeps the chain
    # the way real httpx does (httpx.ConnectError -> ... -> ssl.SSLCertVerificationError).
    def handler(request: httpx.Request) -> httpx.Response:
        raise _tls_error("certificate has expired")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await run_check(client, spec(), resolver=fake_resolver)

    assert asyncio.run(go()).error == "TLS: certificate expired"


@respx.mock
def test_run_checks_runs_concurrently_and_keeps_order():
    respx.get(f"https://{IP}/a").respond(200)
    respx.get(f"https://{IP}/b").respond(500)
    specs = [
        spec(id="A", check_url="https://example.com/a"),
        spec(id="B", check_url="https://example.com/b"),
    ]
    results, skipped = asyncio.run(run_checks(specs, resolver=fake_resolver))
    assert [r.product_id for r in results] == ["A", "B"]
    assert [r.ok for r in results] == [True, False]
    assert skipped == []


@respx.mock
def test_run_checks_budget_skips_instead_of_failing():
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2)
        return httpx.Response(200)

    respx.get(f"https://{IP}/fast").respond(200)
    respx.get(f"https://{IP}/slow").mock(side_effect=slow)
    specs = [
        spec(id="FAST", check_url="https://example.com/fast"),
        spec(id="SLOW", check_url="https://example.com/slow"),
    ]
    results, skipped = asyncio.run(run_checks(specs, resolver=fake_resolver, budget_s=0.2))
    assert [r.product_id for r in results] == ["FAST"]
    assert skipped == ["SLOW"]


def test_run_checks_with_nothing_due():
    assert asyncio.run(run_checks([], resolver=fake_resolver)) == ([], [])
