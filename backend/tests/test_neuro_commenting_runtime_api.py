from __future__ import annotations

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroAttemptStatus,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
    new_id,
)
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account, seed_two_workspaces


def _runtime_seed(db_session):
    account = seed_account(db_session, external_ref="+15550106001")
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Runtime API", "dry_run": False, "send_mode": "manual_approval"},
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
        payload={"channel_ref": "@example", "discussion_chat_id": "discussion-1"},
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
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        account_id=account.id,
        observed_post_id=observed.id,
        generated_text="Интересно.",
        final_text="Интересно.",
        safety_status=NeuroSafetyStatus.PASSED.value,
        approval_status=NeuroGeneratedApprovalStatus.PENDING.value,
    )
    db_session.add_all([observed, comment])
    db_session.flush()
    _approved, attempt = ApprovalService().approve_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    db_session.commit()
    return campaign, target, observed, comment, attempt


def test_observed_posts_and_attempts_are_paginated(app_client, db_session) -> None:
    campaign, _target, observed, _comment, attempt = _runtime_seed(db_session)

    observed_response = app_client.get(
        "/api/neuro-commenting/observed-posts", params={"campaign_id": campaign.id}
    )
    attempt_response = app_client.get(
        "/api/neuro-commenting/attempts", params={"campaign_id": campaign.id}
    )
    observed_get = app_client.get(f"/api/neuro-commenting/observed-posts/{observed.id}")
    attempt_get = app_client.get(f"/api/neuro-commenting/attempts/{attempt.id}")

    assert observed_response.status_code == 200
    assert observed_response.json()["items"][0]["id"] == observed.id
    assert attempt_response.status_code == 200
    assert attempt_response.json()["items"][0]["id"] == attempt.id
    assert observed_get.status_code == 200
    assert attempt_get.status_code == 200


def test_observe_and_refresh_endpoints_return_accepted_payload(
    app_client, db_session, monkeypatch
) -> None:
    campaign, target, _observed, _comment, _attempt = _runtime_seed(db_session)
    monkeypatch.setattr(
        "app.api.neuro_commenting.enqueue_neuro_observe_campaign", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "app.api.neuro_commenting.enqueue_neuro_observe_target", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "app.api.neuro_commenting.enqueue_neuro_refresh_target_metadata", lambda *a, **k: True
    )

    campaign_observe = app_client.post(f"/api/neuro-commenting/campaigns/{campaign.id}/observe")
    target_observe = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign.id}/targets/{target.id}/observe",
        json={"generate": False},
    )
    refresh = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign.id}/targets/{target.id}/refresh-metadata"
    )

    assert campaign_observe.status_code == 202
    assert campaign_observe.json()["queue_name"] == "neuro_comment_jobs"
    assert target_observe.status_code == 202
    assert refresh.status_code == 202


def test_generate_and_send_endpoints_return_controlled_results(
    app_client, db_session, monkeypatch
) -> None:
    _campaign, _target, observed, comment, _attempt = _runtime_seed(db_session)
    monkeypatch.setattr(
        "app.api.neuro_commenting.enqueue_neuro_generate_comment", lambda *a, **k: True
    )

    generate = app_client.post(f"/api/neuro-commenting/observed-posts/{observed.id}/generate")
    send = app_client.post(f"/api/neuro-commenting/generated-comments/{comment.id}/send")

    assert generate.status_code == 202
    assert send.status_code == 409
    assert send.json()["error_code"] == "NEURO_COMMENT_SEND_DISABLED"


def test_generate_force_uses_distinct_queue_job_id(app_client, db_session, monkeypatch) -> None:
    _campaign, _target, observed, _comment, _attempt = _runtime_seed(db_session)
    captured: list[dict[str, object]] = []

    def enqueue(*args, **kwargs):
        _ = args
        captured.append(kwargs)
        return True

    monkeypatch.setattr("app.api.neuro_commenting.enqueue_neuro_generate_comment", enqueue)

    normal = app_client.post(f"/api/neuro-commenting/observed-posts/{observed.id}/generate")
    forced = app_client.post(
        f"/api/neuro-commenting/observed-posts/{observed.id}/generate",
        json={"force": True},
    )

    assert normal.status_code == 202
    assert forced.status_code == 202
    assert normal.json()["job_id"] == f"neuro-generate-{observed.id}"
    assert forced.json()["job_id"].startswith(f"neuro-generate-force-{observed.id}-")
    assert captured[0]["force"] is False
    assert captured[1]["force"] is True
    assert captured[0]["job_id"] != captured[1]["job_id"]


def test_sync_send_is_disabled_outside_local_env(app_client, db_session, monkeypatch) -> None:
    _campaign, _target, _observed, comment, _attempt = _runtime_seed(db_session)
    monkeypatch.setattr("app.api.neuro_commenting.settings.app_env", "production")

    response = app_client.post(
        f"/api/neuro-commenting/generated-comments/{comment.id}/send",
        json={"enqueue": False},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "NEURO_COMMENT_SYNC_SEND_DISABLED"


def test_existing_attempt_is_revalidated_before_enqueue(
    app_client, db_session, monkeypatch
) -> None:
    _campaign, _target, _observed, comment, _attempt = _runtime_seed(db_session)
    comment.approval_status = NeuroGeneratedApprovalStatus.REJECTED.value
    db_session.commit()
    enqueued = False

    def enqueue(*args, **kwargs):
        nonlocal enqueued
        _ = (args, kwargs)
        enqueued = True
        return True

    monkeypatch.setattr("app.api.neuro_commenting.enqueue_neuro_send_attempt", enqueue)

    response = app_client.post(f"/api/neuro-commenting/generated-comments/{comment.id}/send")

    assert response.status_code == 400
    assert response.json()["error_code"] == "COMMENT_NOT_APPROVED"
    assert enqueued is False


def test_sent_attempt_is_idempotent_and_not_requeued(app_client, db_session, monkeypatch) -> None:
    _campaign, _target, _observed, comment, attempt = _runtime_seed(db_session)
    attempt.status = NeuroAttemptStatus.SENT.value
    attempt.telegram_message_id = "already-sent"
    db_session.commit()
    enqueued = False

    def enqueue(*args, **kwargs):
        nonlocal enqueued
        _ = (args, kwargs)
        enqueued = True
        return True

    monkeypatch.setattr("app.api.neuro_commenting.enqueue_neuro_send_attempt", enqueue)

    response = app_client.post(f"/api/neuro-commenting/generated-comments/{comment.id}/send")

    assert response.status_code == 200
    assert response.json()["attempt"]["telegram_message_id"] == "already-sent"
    assert enqueued is False


def test_runtime_enqueue_failure_returns_503(app_client, db_session, monkeypatch) -> None:
    campaign, _target, _observed, _comment, _attempt = _runtime_seed(db_session)
    monkeypatch.setattr(
        "app.api.neuro_commenting.enqueue_neuro_observe_campaign", lambda *a, **k: False
    )

    response = app_client.post(f"/api/neuro-commenting/campaigns/{campaign.id}/observe")

    assert response.status_code == 503
    assert response.json()["error_code"] == "QUEUE_UNAVAILABLE"
    assert (
        db_session.query(NeuroCommentEvent)
        .filter_by(event_type="observe_failed", campaign_id=campaign.id)
        .count()
        == 1
    )


def test_runtime_unknown_query_params_are_rejected(app_client, db_session) -> None:
    _runtime_seed(db_session)

    for endpoint in ("/api/neuro-commenting/observed-posts", "/api/neuro-commenting/attempts"):
        response = app_client.get(endpoint, params={"unexpected": "1"})
        assert response.status_code == 422
        assert response.json()["error_code"] == "HTTP_ERROR"


def test_runtime_endpoints_are_workspace_scoped(app_client, db_session) -> None:
    _own, foreign = seed_two_workspaces(db_session)
    foreign_campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=foreign,
        actor_user_id="foreign-user",
        payload={"name": "Foreign"},
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=foreign_campaign.id,
        workspace_id=foreign,
        actor_user_id="foreign-user",
        payload={"channel_ref": "@foreign"},
    )
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=foreign_campaign.id,
        target_id=target.id,
        source_chat_id="foreign-chat",
        source_message_id="foreign-msg",
    )
    db_session.add(observed)
    db_session.commit()

    response = app_client.get(f"/api/neuro-commenting/observed-posts/{observed.id}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "OBSERVED_POST_NOT_FOUND"
