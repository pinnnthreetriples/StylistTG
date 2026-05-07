import logging

from app.logging_utils import _build_betterstack_handler, _normalize_betterstack_host


def test_betterstack_handler_is_disabled_without_source_config(monkeypatch):
    monkeypatch.delenv("BETTERSTACK_SOURCE_TOKEN", raising=False)
    monkeypatch.delenv("BETTERSTACK_INGESTING_HOST", raising=False)

    assert (
        _build_betterstack_handler(
            source_token=None,
            ingesting_host=None,
            timeout_seconds=None,
            level=logging.INFO,
        )
        is None
    )


def test_betterstack_handler_uses_env_without_exposing_token(monkeypatch):
    monkeypatch.setenv("BETTERSTACK_SOURCE_TOKEN", "source-token")
    monkeypatch.setenv("BETTERSTACK_INGESTING_HOST", "in.logs.betterstack.com")

    handler = _build_betterstack_handler(
        source_token=None,
        ingesting_host=None,
        timeout_seconds=1.5,
        level=logging.WARNING,
    )

    assert handler is not None
    assert handler.level == logging.WARNING
    assert getattr(handler, "ingesting_host") == "https://in.logs.betterstack.com"
    assert getattr(handler, "timeout_seconds") == 1.5


def test_betterstack_host_normalization():
    assert _normalize_betterstack_host("in.logs.betterstack.com/") == "https://in.logs.betterstack.com"
    assert _normalize_betterstack_host("https://example.com/") == "https://example.com"
