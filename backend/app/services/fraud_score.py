"""Fraud Score provider interface.

Оценивает риск прокси (geo-match со страной номера, тип прокси,
исторический fraud-score) перед live-прогревом. В Фазе 0a поставляется
только Mock, реальный провайдер (IPQualityScore/Scamalytics/proxycheck.io)
подключается в Фазе 4e отдельным PR.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import Settings, settings
from app.models import ProxyCategory


@dataclass(frozen=True)
class ProxyAssessmentInput:
    host: str
    port: int
    proxy_protocol: str  # socks5 / http (из AccountProxy.proxy_type)
    proxy_category: str = ProxyCategory.UNKNOWN.value
    phone_country_code: str | None = None
    expected_country_code: str | None = None


@dataclass(frozen=True)
class FraudAssessment:
    provider: str
    ok: bool
    score: int  # 0..100, чем выше тем подозрительнее
    verdict: str  # ok | warn | block | unknown
    reason_code: str | None
    message: str | None
    geo_match: bool | None
    proxy_category_detected: str | None


class FraudScoreProvider(Protocol):
    provider_name: str

    def is_available(self) -> bool:
        ...

    def evaluate_proxy(self, request: ProxyAssessmentInput) -> FraudAssessment:
        ...


class MockFraudScoreProvider:
    """Mock, не делающий внешних вызовов.

    Логика:
    * Если `proxy_category == 'datacenter'` — `warn`.
    * Если `phone_country_code` и `expected_country_code` оба заданы и не совпадают — `block`.
    * Иначе `ok` с нулевым score.
    """

    provider_name = "mock"

    def is_available(self) -> bool:
        return True

    def evaluate_proxy(self, request: ProxyAssessmentInput) -> FraudAssessment:
        phone_country = (request.phone_country_code or "").strip().upper()
        expected_country = (request.expected_country_code or "").strip().upper()
        geo_match: bool | None = None
        if phone_country and expected_country:
            geo_match = phone_country == expected_country
            if not geo_match:
                return FraudAssessment(
                    provider=self.provider_name,
                    ok=False,
                    score=80,
                    verdict="block",
                    reason_code="proxy_geo_mismatch",
                    message=(
                        f"phone country {phone_country} does not match proxy country {expected_country}"
                    ),
                    geo_match=False,
                    proxy_category_detected=request.proxy_category,
                )
        if request.proxy_category == ProxyCategory.DATACENTER.value:
            return FraudAssessment(
                provider=self.provider_name,
                ok=True,
                score=40,
                verdict="warn",
                reason_code="proxy_datacenter",
                message="datacenter proxies raise ban risk in 2026 environment",
                geo_match=geo_match,
                proxy_category_detected=request.proxy_category,
            )
        return FraudAssessment(
            provider=self.provider_name,
            ok=True,
            score=0,
            verdict="ok",
            reason_code=None,
            message=None,
            geo_match=geo_match,
            proxy_category_detected=request.proxy_category,
        )


class UnavailableFraudScoreProvider:
    provider_name = "unavailable"

    def is_available(self) -> bool:
        return False

    def evaluate_proxy(self, request: ProxyAssessmentInput) -> FraudAssessment:
        return FraudAssessment(
            provider=self.provider_name,
            ok=True,
            score=0,
            verdict="unknown",
            reason_code=None,
            message="fraud score provider is not configured",
            geo_match=None,
            proxy_category_detected=request.proxy_category,
        )


def build_fraud_score_provider(config: Settings = settings) -> FraudScoreProvider:
    """Factory.

    В Фазе 0a всегда Mock. В Фазе 4e здесь появится ветка по env
    `WARMUP_FRAUD_PROVIDER` для реального адаптера.
    """
    _ = config
    return MockFraudScoreProvider()
