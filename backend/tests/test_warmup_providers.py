"""Tests for pluggable warmup adapters: text provider + fraud score."""
from __future__ import annotations

from app.adapters.warmup_text_provider import (
    MockWarmupTextProvider,
    TextVariationRequest,
    build_warmup_text_provider,
)
from app.models import ProxyCategory
from app.services.fraud_score import (
    MockFraudScoreProvider,
    ProxyAssessmentInput,
    build_fraud_score_provider,
)


# ---------------------------------------------------------------------------
# WarmupTextProvider
# ---------------------------------------------------------------------------


def test_text_provider_factory_default_is_mock() -> None:
    provider = build_warmup_text_provider()
    assert provider.provider_name == MockWarmupTextProvider.provider_name
    assert provider.is_available() is True


def test_text_provider_generate_bio_is_deterministic() -> None:
    provider = MockWarmupTextProvider()
    a = provider.generate_bio(seed="account-123")
    b = provider.generate_bio(seed="account-123")
    assert a == b
    c = provider.generate_bio(seed="account-OTHER")
    assert c.rendered  # smoke: non-empty for different seed
    # Разные seed -> ожидаем шанс отличия (не гарантия, но 1/5 шаблонов — слишком мало);
    # проверяем, что результат стабилен при одинаковом seed.


def test_text_provider_rewrite_is_deterministic_and_keeps_template() -> None:
    provider = MockWarmupTextProvider()
    request = TextVariationRequest(template="Привет!", seed="seed-42")
    result_first = provider.rewrite_text(request)
    result_second = provider.rewrite_text(request)
    assert result_first == result_second
    assert result_first.template == "Привет!"
    assert result_first.rendered  # не пустой


def test_compose_p2p_uses_pool_when_template_empty() -> None:
    provider = MockWarmupTextProvider()
    request = TextVariationRequest(template="", seed="pair-xyz")
    result = provider.compose_p2p_message(request)
    assert result.rendered
    assert result.template  # заполнилось из пула


def test_compose_spam_bot_reply_returns_neutral_text() -> None:
    provider = MockWarmupTextProvider()
    request = TextVariationRequest(template="", seed="spam-bot-1")
    result = provider.compose_spam_bot_reply(request)
    assert result.rendered
    assert "реклам" in result.rendered or "общаюсь" in result.rendered or "пользователь" in result.rendered


# ---------------------------------------------------------------------------
# FraudScoreProvider
# ---------------------------------------------------------------------------


def test_fraud_provider_factory_default_is_mock() -> None:
    provider = build_fraud_score_provider()
    assert provider.provider_name == MockFraudScoreProvider.provider_name
    assert provider.is_available() is True


def test_fraud_mock_ok_when_residential_and_geo_matches() -> None:
    provider = MockFraudScoreProvider()
    result = provider.evaluate_proxy(
        ProxyAssessmentInput(
            host="1.2.3.4",
            port=1080,
            proxy_protocol="socks5",
            proxy_category=ProxyCategory.RESIDENTIAL.value,
            phone_country_code="ru",
            expected_country_code="RU",
        )
    )
    assert result.ok is True
    assert result.verdict == "ok"
    assert result.geo_match is True


def test_fraud_mock_warns_on_datacenter() -> None:
    provider = MockFraudScoreProvider()
    result = provider.evaluate_proxy(
        ProxyAssessmentInput(
            host="1.2.3.4",
            port=1080,
            proxy_protocol="http",
            proxy_category=ProxyCategory.DATACENTER.value,
        )
    )
    assert result.verdict == "warn"
    assert result.reason_code == "proxy_datacenter"
    assert result.ok is True  # warn не блокирует, но заметный score


def test_fraud_mock_blocks_on_geo_mismatch() -> None:
    provider = MockFraudScoreProvider()
    result = provider.evaluate_proxy(
        ProxyAssessmentInput(
            host="1.2.3.4",
            port=1080,
            proxy_protocol="socks5",
            proxy_category=ProxyCategory.RESIDENTIAL.value,
            phone_country_code="RU",
            expected_country_code="NL",
        )
    )
    assert result.ok is False
    assert result.verdict == "block"
    assert result.reason_code == "proxy_geo_mismatch"
    assert result.geo_match is False


def test_fraud_mock_unknown_when_no_geo_hints() -> None:
    provider = MockFraudScoreProvider()
    result = provider.evaluate_proxy(
        ProxyAssessmentInput(
            host="1.2.3.4",
            port=1080,
            proxy_protocol="socks5",
            proxy_category=ProxyCategory.UNKNOWN.value,
        )
    )
    assert result.verdict == "ok"
    assert result.geo_match is None
