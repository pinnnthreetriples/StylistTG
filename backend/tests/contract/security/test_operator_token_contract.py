from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _patch_runtime_mode_without_operator_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_mode", "local")
    monkeypatch.setattr(settings, "operator_api_token", "contract-token")

    with TestClient(app) as client:
        return client.patch("/api/auth/runtime-mode", json={"tdlib_use_test_dc": False})


@pytest.mark.contract
@pytest.mark.security
def test_mutating_operator_api_requires_operator_token_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _patch_runtime_mode_without_operator_token(monkeypatch)

    assert response.status_code == 401
    assert response.json() == {"detail": "operator token is required"}
