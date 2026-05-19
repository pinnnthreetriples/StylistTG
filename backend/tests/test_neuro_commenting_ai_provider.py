from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    new_id,
)
from app.services.neuro_commenting.ai_comment_generator import (
    AICommentGenerationError,
    FakeAICommentProvider,
    build_ai_comment_generator,
)
from app.services.neuro_commenting.ai_provider_openai import OpenAICompatibleCommentProvider
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.enums import NeuroObservedPostStatus
from app.services.neuro_commenting.jobs import generate_comment, run_generate_comment
from app.services.neuro_commenting.prompt_builder import BuiltPrompt
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account


def _prompt() -> BuiltPrompt:
    return BuiltPrompt(
        system_prompt="system prompt must not leak",
        user_prompt="Пост: Тестовый пост",
        prompt_version=1,
    )


def _settings(**overrides: object) -> SimpleNamespace:
    values = {
        "neuro_comment_ai_provider": "openai_compatible",
        "neuro_comment_ai_base_url": "https://ai.example.test",
        "neuro_comment_ai_api_key": "secret-token",
        "neuro_comment_ai_model": "model-a",
        "neuro_comment_ai_timeout_seconds": 1.0,
        "neuro_comment_ai_max_retries": 2,
        "neuro_comment_ai_max_tokens": 120,
        "neuro_comment_ai_temperature": 0.7,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _provider(handler) -> OpenAICompatibleCommentProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatibleCommentProvider(
        settings=_settings(), client=client, sleep=lambda _seconds: None
    )


def test_fake_provider_is_deterministic() -> None:
    provider = FakeAICommentProvider()

    first = provider.generate_comment(_prompt())
    second = provider.generate_comment(_prompt())

    assert first == second
    assert first.provider == "fake"
    assert first.model == "fake-neuro-comment-v1"


def test_openai_compatible_provider_success_records_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://ai.example.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret-token"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "  Отличная мысль  "}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            },
        )

    result = _provider(handler).generate_comment(_prompt())

    assert result.text == "Отличная мысль"
    assert result.provider == "openai_compatible"
    assert result.model == "model-a"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 3
    assert result.total_tokens == 13


def test_openai_timeout_maps_to_domain_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    with pytest.raises(AICommentGenerationError) as exc:
        _provider(handler).generate_comment(_prompt())

    assert exc.value.error_code == "AI_PROVIDER_TIMEOUT"
    assert "secret-token" not in str(exc.value)


def test_openai_rate_limit_exceeded_retries_then_maps_to_rate_limited() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"error": {"message": "slow down secret-token"}})

    with pytest.raises(AICommentGenerationError) as exc:
        _provider(handler).generate_comment(_prompt())

    assert calls == 3
    assert exc.value.error_code == "AI_PROVIDER_RATE_LIMITED"
    assert "secret-token" not in str(exc.value)


def test_openai_5xx_retries_then_request_failed() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": {"message": "server failed"}})

    with pytest.raises(AICommentGenerationError) as exc:
        _provider(handler).generate_comment(_prompt())

    assert calls == 3
    assert exc.value.error_code == "AI_PROVIDER_REQUEST_FAILED"


def test_openai_malformed_and_empty_responses_are_rejected() -> None:
    malformed = _provider(lambda _request: httpx.Response(200, json={"choices": []}))
    empty = _provider(
        lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": "  "}}]})
    )

    with pytest.raises(AICommentGenerationError) as malformed_exc:
        malformed.generate_comment(_prompt())
    with pytest.raises(AICommentGenerationError) as empty_exc:
        empty.generate_comment(_prompt())

    assert malformed_exc.value.error_code == "AI_PROVIDER_BAD_RESPONSE"
    assert empty_exc.value.error_code == "AI_EMPTY_RESPONSE"


def test_build_ai_comment_generator_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unknown AI provider"):
        build_ai_comment_generator(_settings(neuro_comment_ai_provider="unknown"))


def test_generation_job_writes_provider_model_and_token_usage_to_event(db_session) -> None:
    account = seed_account(db_session, external_ref="+15550103001")
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "AI campaign"},
    )
    campaign.status = "running"
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@example"},
    )
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="chat-1",
        source_message_id="msg-1",
        post_text="Новый пост",
        language="ru",
    )
    db_session.add(observed)
    db_session.commit()

    comment = generate_comment(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        observed_post_id=observed.id,
    )
    db_session.commit()

    completed = (
        db_session.query(NeuroCommentEvent)
        .filter_by(event_type="ai_generation_completed", generated_comment_id=comment.id)
        .one()
    )
    assert completed.data_json["provider"] == "fake"
    assert completed.data_json["model"] == "fake-neuro-comment-v1"
    assert "system prompt" not in str(completed.data_json)

    duplicate = generate_comment(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        observed_post_id=observed.id,
    )
    forced = generate_comment(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        observed_post_id=observed.id,
        force=True,
    )
    db_session.commit()

    assert duplicate.id == comment.id
    assert forced.id != comment.id
    assert (
        db_session.query(NeuroCommentGeneratedComment)
        .filter_by(observed_post_id=observed.id)
        .count()
        == 2
    )


def test_rq_generate_failure_persists_observed_failed_and_event(db_session, monkeypatch) -> None:
    account = seed_account(db_session, external_ref="+15550103002")
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "AI failure campaign"},
    )
    campaign.status = "running"
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@example"},
    )
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="chat-2",
        source_message_id="msg-2",
        post_text="Новый пост",
    )
    db_session.add(observed)
    db_session.commit()

    class FailingGenerator:
        def generate(self, prompt):
            _ = prompt
            raise AICommentGenerationError("AI_PROVIDER_REQUEST_FAILED", "failed")

    monkeypatch.setattr(
        "app.services.neuro_commenting.jobs.build_ai_comment_generator",
        lambda: FailingGenerator(),
    )
    monkeypatch.setattr(
        "app.services.neuro_commenting.jobs.SessionLocal",
        lambda: _ExistingSessionContext(db_session),
    )

    with pytest.raises(AICommentGenerationError):
        run_generate_comment(
            campaign.id,
            DEFAULT_LOCAL_WORKSPACE_ID,
            observed.id,
        )

    db_session.expire_all()
    assert (
        db_session.query(NeuroCommentObservedPost).filter_by(id=observed.id).one().status
        == NeuroObservedPostStatus.FAILED.value
    )
    assert (
        db_session.query(NeuroCommentEvent)
        .filter_by(event_type="ai_generation_failed", observed_post_id=observed.id)
        .count()
        == 1
    )
    assert (
        db_session.query(NeuroCommentGeneratedComment)
        .filter_by(observed_post_id=observed.id)
        .count()
        == 0
    )


class _ExistingSessionContext:
    def __init__(self, session) -> None:
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:
        _ = (exc_type, exc, tb)
        return False
