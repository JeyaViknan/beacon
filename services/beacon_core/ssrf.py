"""SSRF guard (HANDOVER §8.4). Security-critical: every branch is covered by tests.

Beacon fetches URLs that a user typed. Without a guard, "check http://127.0.0.1:9001/..." would let
anyone with the admin password read the Lambda runtime API, or "http://169.254.169.254/" the
instance metadata service on other compute. The rules:

1. Only ``http`` and ``https``; no credentials in the URL.
2. Resolve DNS first and check **every** resolved address; refuse if any is non-public.
3. Connect to the address we checked (``Target.pinned_url``), sending the real hostname in
   ``Host`` and TLS SNI. That closes the DNS-rebinding window between "check" and "connect".
4. Redirects are followed manually (max 3) and each hop goes through steps 1-3 again.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], Awaitable[list[str]]]

BLOCKED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",  # "this network", incl. 0.0.0.0
        "10.0.0.0/8",  # private
        "100.64.0.0/10",  # carrier-grade NAT (shared address space)
        "127.0.0.0/8",  # loopback (Lambda runtime API lives on 127.0.0.1:9001)
        "169.254.0.0/16",  # link-local, incl. 169.254.169.254 metadata
        "172.16.0.0/12",  # private
        "192.0.0.0/24",  # IETF protocol assignments
        "192.168.0.0/16",  # private
        "198.18.0.0/15",  # benchmarking
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved, incl. 255.255.255.255
        "::/128",  # unspecified
        "::1/128",  # loopback
        "fc00::/7",  # unique local (incl. fd00:ec2::254 metadata)
        "fe80::/10",  # link-local
        "ff00::/8",  # multicast
    )
)


class SSRFError(ValueError):
    """The URL or one of its resolved addresses is not allowed."""


class DNSError(SSRFError):
    """The host did not resolve; not a policy violation, but we cannot check it either."""


@dataclass(frozen=True)
class Target:
    """A URL that passed the guard, plus how to reach it safely."""

    url: str
    scheme: str
    host: str
    port: int
    addresses: tuple[str, ...]
    ip: str  # the checked address we connect to
    pinned_url: str  # same URL with the host replaced by ``ip``
    host_header: str  # what to send as Host (includes a non-default port)


def unwrap(ip: IPAddress) -> IPAddress:
    """See through IPv6 forms that embed an IPv4 address (mapped, 6to4, Teredo)."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
        if ip.sixtofour is not None:
            return ip.sixtofour
        if ip.teredo is not None:
            return ip.teredo[1]
    return ip


def is_blocked_ip(address: str | IPAddress) -> bool:
    ip = unwrap(ipaddress.ip_address(address) if isinstance(address, str) else address)
    if any(ip.version == net.version and ip in net for net in BLOCKED_NETWORKS):
        return True
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved


def parse_url(url: str) -> SplitResult:
    """Syntax-level checks only (no DNS)."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise SSRFError("only http:// and https:// URLs are allowed")
    if not parts.hostname:
        raise SSRFError("URL has no host")
    if parts.username is not None or parts.password is not None:
        raise SSRFError("URLs with credentials are not allowed")
    try:
        _ = parts.port
    except ValueError as exc:
        raise SSRFError("invalid port") from exc
    return parts


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


def check_addresses(host: str, addresses: Iterable[str]) -> tuple[str, ...]:
    """Every resolved address must be public; one bad address blocks the whole host."""
    found = tuple(addresses)
    if not found:
        raise DNSError("DNS: host not found")
    for address in found:
        if is_blocked_ip(address):
            raise SSRFError(f"{host} resolves to a non-public address ({address})")
    return found


def _prefer_ipv4(addresses: tuple[str, ...]) -> str:
    # Lambda outside a VPC only has IPv4 egress.
    return next((a for a in addresses if ipaddress.ip_address(a).version == 4), addresses[0])


async def resolve_target(url: str, resolver: Resolver = system_resolver) -> Target:
    """Validate ``url``, resolve its host, check every address and pin one for connecting."""
    parts = parse_url(url)
    default_port = 443 if parts.scheme == "https" else 80
    port = parts.port or default_port

    try:
        literal: IPAddress | None = ipaddress.ip_address(parts.hostname or "")
    except ValueError:
        literal = None

    if literal is not None:
        host = str(literal)
        addresses = check_addresses(host, [host])
    else:
        try:
            host = (parts.hostname or "").encode("idna").decode("ascii")
            resolved = await resolver(host, port)
        except (OSError, UnicodeError) as exc:
            raise DNSError("DNS: host not found") from exc
        addresses = check_addresses(host, resolved)

    def netloc_for(name: str) -> str:
        bracketed = f"[{name}]" if ":" in name else name
        return bracketed if port == default_port else f"{bracketed}:{port}"

    pinned_ip = _prefer_ipv4(addresses)
    return Target(
        url=urlunsplit(parts),
        scheme=parts.scheme,
        host=host,
        port=port,
        addresses=addresses,
        ip=pinned_ip,
        pinned_url=urlunsplit(parts._replace(netloc=netloc_for(pinned_ip))),
        host_header=netloc_for(host),
    )


async def validate_url(url: str, resolver: Resolver = system_resolver) -> None:
    """API-side validation on create/update: same rules as the probe, raises ``SSRFError``."""
    await resolve_target(url, resolver)
