from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen
from urllib.error import URLError

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

from app.config import Settings
from app.errors import AppError


@dataclass(frozen=True)
class SupabaseJwtVerifier:
    jwks_url: str
    issuer: str | None = None
    audience: str | None = None
    cache_ttl_seconds: int = 600
    refresh_on_kid_miss: bool = True
    request_timeout_seconds: float = 5.0
    max_retries: int = 1

    @classmethod
    def from_settings(cls, settings: Settings) -> SupabaseJwtVerifier:
        if not settings.supabase_auth_jwks_url:
            raise AppError(
                status_code=500,
                error_code="SUPABASE_JWKS_NOT_CONFIGURED",
                error_class="configuration",
                message="Supabase JWKS URL is not configured",
            )
        return cls(
            jwks_url=settings.supabase_auth_jwks_url,
            issuer=settings.supabase_auth_issuer,
            audience=settings.supabase_auth_audience,
            cache_ttl_seconds=settings.supabase_auth_jwks_cache_ttl_seconds,
            refresh_on_kid_miss=settings.supabase_auth_jwks_refresh_on_kid_miss,
            request_timeout_seconds=settings.supabase_auth_jwks_request_timeout_seconds,
            max_retries=settings.supabase_auth_jwks_max_retries,
        )

    def verify(self, token: str) -> dict[str, Any]:
        header, payload, signature, signing_input = _split_jwt(token)
        if header.get("alg") != "RS256":
            raise _auth_error("JWT_ALG_UNSUPPORTED", "unsupported JWT algorithm")
        kid = str(header.get("kid") or "")
        try:
            key = _find_jwk(self._cached_jwks(force_refresh=False), kid)
        except AppError as exc:
            if exc.error_code != "JWT_KEY_NOT_FOUND" or not self.refresh_on_kid_miss:
                raise
            key = _find_jwk(self._cached_jwks(force_refresh=True), kid)
        public_key = _rsa_public_key_from_jwk(key)
        try:
            public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise _auth_error("JWT_SIGNATURE_INVALID", "JWT signature is invalid") from exc
        now = int(time.time())
        if int(payload.get("exp", 0)) <= now:
            raise _auth_error("JWT_EXPIRED", "JWT is expired")
        if self.issuer and payload.get("iss") != self.issuer:
            raise _auth_error("JWT_ISSUER_INVALID", "JWT issuer is invalid")
        if self.audience:
            audience = payload.get("aud")
            audiences = audience if isinstance(audience, list) else [audience]
            if self.audience not in audiences:
                raise _auth_error("JWT_AUDIENCE_INVALID", "JWT audience is invalid")
        if not payload.get("sub"):
            raise _auth_error("JWT_SUB_MISSING", "JWT subject is missing")
        return payload

    def _cached_jwks(self, *, force_refresh: bool) -> dict[str, Any]:
        return _get_cached_jwks(
            self.jwks_url,
            ttl_seconds=self.cache_ttl_seconds,
            force_refresh=force_refresh,
            timeout_seconds=self.request_timeout_seconds,
            max_retries=self.max_retries,
        )


_JWKS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def clear_jwks_cache() -> None:
    _JWKS_CACHE.clear()


def _split_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    try:
        header_raw, payload_raw, signature_raw = token.split(".")
        signing_input = f"{header_raw}.{payload_raw}".encode()
        header = json.loads(_b64decode(header_raw))
        payload = json.loads(_b64decode(payload_raw))
        signature = _b64decode(signature_raw)
    except Exception as exc:
        raise _auth_error("JWT_MALFORMED", "JWT is malformed") from exc
    return header, payload, signature, signing_input


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _get_cached_jwks(
    url: str,
    *,
    ttl_seconds: int,
    force_refresh: bool,
    timeout_seconds: float,
    max_retries: int,
) -> dict[str, Any]:
    now = time.time()
    cached = _JWKS_CACHE.get(url)
    if not force_refresh and cached is not None and cached[0] > now:
        return cached[1]
    jwks = _load_jwks(url, timeout_seconds=timeout_seconds, max_retries=max_retries)
    _JWKS_CACHE[url] = (now + max(1, ttl_seconds), jwks)
    return jwks


def _load_jwks(url: str, *, timeout_seconds: float = 5.0, max_retries: int = 1) -> dict[str, Any]:
    attempts = max(0, max_retries) + 1
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            with urlopen(url, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            last_error = exc
    raise _auth_error("JWT_JWKS_FETCH_FAILED", "JWKS fetch failed") from last_error


def _find_jwk(jwks: dict[str, Any], kid: str) -> dict[str, Any]:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise _auth_error("JWT_KEY_NOT_FOUND", "JWT signing key was not found")


def _rsa_public_key_from_jwk(jwk: dict[str, Any]):
    n = int.from_bytes(_b64decode(jwk["n"]), "big")
    e = int.from_bytes(_b64decode(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e=e, n=n).public_key()


def _auth_error(code: str, message: str) -> AppError:
    return AppError(status_code=401, error_code=code, error_class="auth_required", message=message)
