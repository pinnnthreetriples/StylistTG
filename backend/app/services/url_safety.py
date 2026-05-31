from __future__ import annotations

from urllib.parse import urlparse


_LOCAL_HTTP_HOSTS = {"localhost", "127.0.0.1", "::1"}


def require_https_url(url: str, *, field_name: str = "URL") -> str:
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    raise ValueError(f"{field_name} must be an HTTPS URL")


def require_http_url(
    url: str,
    *,
    field_name: str = "URL",
    allow_local_http: bool = False,
) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if allow_local_http and parsed.scheme == "http" and parsed.hostname in _LOCAL_HTTP_HOSTS:
        return url
    raise ValueError(f"{field_name} must be an HTTP(S) URL")
