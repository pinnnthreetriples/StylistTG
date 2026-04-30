from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

from app.config import Settings
from app.errors import AppError


@dataclass(frozen=True)
class SupabaseJwtVerifier:
    jwks_url: str
    issuer: str | None = None
    audience: str | None = None

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
        )

    def verify(self, token: str) -> dict[str, Any]:
        header, payload, signature, signing_input = _split_jwt(token)
        if header.get("alg") != "RS256":
            raise _auth_error("JWT_ALG_UNSUPPORTED", "unsupported JWT algorithm")
        key = _find_jwk(_load_jwks(self.jwks_url), str(header.get("kid") or ""))
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


def _load_jwks(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


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
