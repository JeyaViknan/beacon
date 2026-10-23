"""SSRF guard: every blocked range, every bypass trick we know of, and the pinning behaviour."""

import asyncio

import pytest

from beacon_core.ssrf import (
    DNSError,
    SSRFError,
    is_blocked_ip,
    parse_url,
    resolve_target,
    validate_url,
)


def resolver_for(mapping: dict[str, list[str]]):
    async def resolve(host: str, port: int) -> list[str]:
        if host not in mapping:
            raise OSError("Name or service not known")
        return mapping[host]

    return resolve


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "ip",
    [
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.0.1",
        "192.168.255.255",
        "127.0.0.1",
        "127.0.0.53",
        "127.255.255.254",
        "169.254.169.254",  # AWS / GCP / Azure instance metadata
        "169.254.0.1",
        "169.254.170.2",  # ECS task metadata
        "0.0.0.0",
        "0.1.2.3",
        "100.64.0.1",  # carrier-grade NAT
        "224.0.0.1",  # multicast
        "255.255.255.255",
        "::",
        "::1",
        "fc00::1",
        "fd00:ec2::254",  # EC2 IMDS over IPv6
        "fe80::1",
        "febf::1",  # top of fe80::/10
        "ff02::1",
        "::ffff:10.0.0.1",  # IPv4-mapped private
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
        "2002:a00:1::",  # 6to4 wrapping 10.0.0.1
        "2002:7f00:1::",  # 6to4 wrapping 127.0.0.1
        "2001:0:4136:e378:8000:63bf:80ff:fffe",  # Teredo with client 127.0.0.1
    ],
)
def test_blocked_addresses(ip):
    assert is_blocked_ip(ip) is True


@pytest.mark.parametrize(
    "ip",
    [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.216.34",
        "13.235.0.1",  # an ap-south-1 public range
        "11.0.0.1",
        "172.15.255.255",  # just below 172.16/12
        "172.32.0.1",  # just above 172.16/12
        "192.169.0.1",
        "169.255.0.1",
        "2606:4700:4700::1111",
        "2001:4860:4860::8888",
    ],
)
def test_public_addresses_allowed(ip):
    assert is_blocked_ip(ip) is False


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "file:///etc/passwd",
        "gopher://example.com",
        "javascript:alert(1)",
        "dict://example.com:11211/",
        "example.com/no-scheme",
        "http://",
        "https:///path-only",
        "http://user:pass@example.com/",
        "http://user@example.com/",
        "http://example.com:99999/",
    ],
)
def test_parse_url_rejects(url):
    with pytest.raises(SSRFError):
        parse_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:9001/2018-06-01/runtime/invocation/next",  # Lambda runtime API
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "http://[::1]:8080/",
        "http://[fd00:ec2::254]/",
        "http://[::ffff:127.0.0.1]/",
        "http://10.0.0.5/admin",
        "http://0.0.0.0/",
    ],
)
def test_ip_literal_urls_are_blocked_without_dns(url):
    async def no_dns(host: str, port: int) -> list[str]:
        raise AssertionError("IP literals must not be resolved")

    with pytest.raises(SSRFError, match="non-public"):
        run(resolve_target(url, no_dns))


@pytest.mark.parametrize(
    ("host", "resolved"),
    [
        ("localhost", ["127.0.0.1", "::1"]),
        ("2130706433", ["127.0.0.1"]),  # decimal-encoded 127.0.0.1
        ("0x7f000001", ["127.0.0.1"]),  # hex-encoded
        ("127.1", ["127.0.0.1"]),  # short form
        ("metadata.internal", ["169.254.169.254"]),
        ("rebind.example", ["93.184.216.34", "10.0.0.1"]),  # one bad record blocks the host
        ("v6only.example", ["fd12::1"]),
    ],
)
def test_hostnames_resolving_to_private_addresses_are_blocked(host, resolved):
    with pytest.raises(SSRFError, match="non-public"):
        run(resolve_target(f"http://{host}/", resolver_for({host: resolved})))


def test_dns_failure_is_a_dns_error():
    with pytest.raises(DNSError, match="DNS: host not found"):
        run(resolve_target("https://nope.invalid/", resolver_for({})))


def test_empty_dns_answer_is_a_dns_error():
    with pytest.raises(DNSError):
        run(resolve_target("https://empty.example/", resolver_for({"empty.example": []})))


def test_public_host_is_pinned_to_the_checked_ip():
    target = run(
        resolve_target(
            "https://example.com/health?x=1",
            resolver_for({"example.com": ["2606:2800:220:1::1", "93.184.216.34"]}),
        )
    )
    assert target.pinned_url == "https://93.184.216.34/health?x=1"  # IPv4 preferred
    assert target.host_header == "example.com"
    assert target.host == "example.com"
    assert target.port == 443
    assert target.addresses == ("2606:2800:220:1::1", "93.184.216.34")


def test_non_default_port_is_kept_in_url_and_host_header():
    target = run(
        resolve_target("http://example.com:8080/x", resolver_for({"example.com": ["1.2.3.4"]}))
    )
    assert target.pinned_url == "http://1.2.3.4:8080/x"
    assert target.host_header == "example.com:8080"


def test_ipv6_only_host_is_bracketed():
    target = run(
        resolve_target("https://v6.example/", resolver_for({"v6.example": ["2606:4700::1"]}))
    )
    assert target.pinned_url == "https://[2606:4700::1]/"


def test_public_ip_literal_is_allowed():
    target = run(resolve_target("http://93.184.216.34:8443/", resolver_for({})))
    assert target.pinned_url == "http://93.184.216.34:8443/"
    assert target.host_header == "93.184.216.34:8443"


def test_unicode_hostname_is_idna_encoded():
    target = run(
        resolve_target(
            "https://bücher.example/", resolver_for({"xn--bcher-kva.example": ["1.2.3.4"]})
        )
    )
    assert target.host == "xn--bcher-kva.example"


def test_validate_url_uses_the_same_rules():
    run(validate_url("https://ok.example/", resolver_for({"ok.example": ["8.8.8.8"]})))
    with pytest.raises(SSRFError):
        run(validate_url("https://bad.example/", resolver_for({"bad.example": ["192.168.1.1"]})))


def test_system_resolver_resolves_ip_literals_offline():
    from beacon_core.ssrf import system_resolver

    assert run(system_resolver("127.0.0.1", 80)) == ["127.0.0.1"]
