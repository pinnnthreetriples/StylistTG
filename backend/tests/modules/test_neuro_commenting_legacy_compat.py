from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    ("legacy_path", "canonical_path"),
    [
        (
            "app.services.neuro_commenting.ai_comment_generator",
            "app.modules.neuro_commenting.ai_comment_generator",
        ),
        (
            "app.services.neuro_commenting.jobs",
            "app.modules.neuro_commenting.job_handlers",
        ),
        (
            "app.services.neuro_commenting.live_readiness_service",
            "app.modules.neuro_commenting.live_readiness_service",
        ),
        (
            "app.services.neuro_commenting.repository",
            "app.modules.neuro_commenting.repository",
        ),
        (
            "app.services.neuro_commenting.sender_service",
            "app.modules.neuro_commenting.sender_service",
        ),
        (
            "app.services.neuro_commenting.tdlib_runtime",
            "app.modules.neuro_commenting.tdlib_runtime",
        ),
    ],
)
def test_legacy_neuro_commenting_service_modules_alias_canonical_modules(
    legacy_path: str, canonical_path: str
) -> None:
    assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)
