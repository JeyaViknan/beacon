"""Single-admin authentication: argon2id password hash, HS256 JWT, login throttle (HANDOVER §12)."""

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from beacon_core.timeutil import parse_iso, to_iso

TOKEN_TTL = timedelta(days=30)
MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=15)
ISSUER = "beacon"
_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters


class AuthError(Exception):
    """Missing, malformed, expired or forged credentials."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def issue_token(secret: str, now: datetime) -> tuple[str, str]:
    expires = now + TOKEN_TTL
    claims = {
        "sub": "admin",
        "iss": ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(claims, secret, algorithm="HS256"), to_iso(expires)


def verify_token(secret: str, token: str, now: datetime) -> dict[str, Any]:
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],  # pinned: never let the token pick its own algorithm
            issuer=ISSUER,
            # Time claims are checked below against the injected ``now`` so this stays testable.
            options={
                "require": ["exp", "iat", "sub", "iss"],
                "verify_exp": False,
                "verify_iat": False,
            },
        )
    except jwt.PyJWTError as exc:
        raise AuthError("invalid token") from exc
    epoch = int(now.timestamp())
    if claims["exp"] <= epoch:
        raise AuthError("token expired")
    if claims["iat"] > epoch + 60:
        raise AuthError("token issued in the future")
    if claims["sub"] != "admin":
        raise AuthError("invalid subject")
    return claims


def bearer_token(header: str | None) -> str:
    if not header:
        raise AuthError("missing Authorization header")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("expected a Bearer token")
    return token.strip()


def same_secret(expected: str, given: str | None) -> bool:
    """Constant-time comparison so response timing does not leak the secret."""
    return bool(expected) and given is not None and hmac.compare_digest(expected, given)


@dataclass(frozen=True)
class Throttle:
    failures: int = 0
    locked_until: str | None = None

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "Throttle":
        return cls(failures=int(item.get("failures", 0)), locked_until=item.get("lockedUntil"))

    def retry_after(self, now: datetime) -> int:
        """Seconds until login is allowed again (0 = allowed now)."""
        if not self.locked_until:
            return 0
        return max(0, int((parse_iso(self.locked_until) - now).total_seconds()))

    def after_failure(self, now: datetime) -> "Throttle":
        if self.retry_after(now) == 0 and self.locked_until:
            # Lock expired: start counting from scratch.
            return Throttle(failures=1)
        failures = self.failures + 1
        if failures >= MAX_FAILURES:
            return Throttle(failures=failures, locked_until=to_iso(now + LOCKOUT))
        return Throttle(failures=failures)
