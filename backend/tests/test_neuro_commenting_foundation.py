from __future__ import annotations

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroAttemptStatus,
    NeuroCommentAttempt,
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
from app.services.neuro_commenting.jobs import generate_comment
from app.services.neuro_commenting.safety_policy import SafetyPolicy
from app.services.neuro_commenting.sender_service import SenderService
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account, seed_two_workspaces


def test_create_campaign_defaults_to_safe_manual_dry_run(db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Launch comments"},
    )
    db_session.commit()

    assert campaign.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert campaign.dry_run is True
    assert campaign.auto_send_enabled is False
    assert campaign.send_mode == "dry_run"
    assert db_session.query(NeuroCommentEvent).filter_by(event_type="campaign_created").count() == 1


def test_workspace_isolation_prevents_foreign_campaign_read(db_session) -> None:
    _own_workspace, foreign_workspace = seed_two_workspaces(db_session)
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Own campaign"},
    )
    db_session.commit()

    try:
        CampaignService().start_campaign(
            db_session,
            campaign_id=campaign.id,
            workspace_id=foreign_workspace,
            actor_user_id="foreign-user",
        )
    except ValueError as exc:
        assert str(exc) == "campaign not found"
    else:
        raise AssertionError("foreign workspace accessed campaign")


def test_cannot_add_foreign_account_to_campaign(db_session) -> None:
    _own_workspace, foreign_workspace = seed_two_workspaces(db_session)
    foreign_account = seed_account(
        db_session,
        external_ref="+15550109999",
        workspace_id=foreign_workspace,
    )
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Own campaign"},
    )
    db_session.commit()

    try:
        CampaignAccountService().add_account(
            db_session,
            campaign_id=campaign.id,
            account_id=foreign_account.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            actor_user_id="user-1",
        )
    except ValueError as exc:
        assert str(exc) == "account not found"
    else:
        raise AssertionError("foreign account was added")


def test_add_target_creates_target_and_event(db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Own campaign"},
    )

    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@example", "keywords": [" AI "]},
    )
    db_session.commit()

    assert target.channel_ref == "@example"
    assert target.keywords == ["ai"]
    assert db_session.query(NeuroCommentEvent).filter_by(event_type="target_added").count() == 1


def test_generate_comment_creates_pending_comment_and_event(db_session) -> None:
    account = seed_account(db_session, external_ref="+15550102001")
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Own campaign"},
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
        post_text="Новый пост о продукте",
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

    assert comment.approval_status == NeuroGeneratedApprovalStatus.PENDING.value
    assert comment.safety_status == NeuroSafetyStatus.PASSED.value
    assert comment.account_id == account.id
    assert (
        db_session.query(NeuroCommentEvent).filter_by(event_type="comment_generated").count() == 1
    )


def test_approve_comment_creates_attempt_but_does_not_send(db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Own campaign"},
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        generated_text="Интересная мысль.",
        final_text="Интересная мысль.",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    db_session.add(comment)
    db_session.commit()

    approved, attempt = ApprovalService().approve_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    db_session.commit()

    assert approved.approval_status == NeuroGeneratedApprovalStatus.APPROVED.value
    assert attempt.status == NeuroAttemptStatus.CREATED.value
    assert db_session.query(NeuroCommentAttempt).count() == 1


def test_reject_and_edit_comment(db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Own campaign"},
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        generated_text="Первый вариант",
        final_text="Первый вариант",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    db_session.add(comment)
    db_session.commit()

    edited = ApprovalService().edit_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        edited_text="Новый вариант",
    )
    rejected = ApprovalService().reject_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        reason="Не подходит",
    )
    db_session.commit()

    assert edited.final_text == "Новый вариант"
    assert rejected.approval_status == NeuroGeneratedApprovalStatus.REJECTED.value
    assert rejected.rejected_reason == "Не подходит"


def test_sender_service_blocks_auto_send_by_default(db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Own campaign"},
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        generated_text="Интересно.",
        final_text="Интересно.",
    )

    prepared = SenderService().prepare_send(campaign=campaign, comment=comment)

    assert prepared.allowed is False
    assert prepared.reason == "auto_send_disabled"


def test_safety_policy_blocks_links_and_too_long_text(db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Own campaign"},
    )
    policy = SafetyPolicy()

    link_decision = policy.check(text="Посмотри https://example.test", campaign=campaign)
    long_decision = policy.check(text="а" * 121, campaign=campaign)

    assert link_decision.status == NeuroSafetyStatus.BLOCKED
    assert link_decision.reason == "links_blocked"
    assert long_decision.status == NeuroSafetyStatus.BLOCKED
    assert long_decision.reason == "too_long"


def test_api_does_not_return_foreign_workspace_campaign(app_client, db_session) -> None:
    _own_workspace, foreign_workspace = seed_two_workspaces(db_session)
    foreign_campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=foreign_workspace,
        actor_user_id="foreign-user",
        payload={"name": "Foreign campaign"},
    )
    db_session.commit()

    response = app_client.get(f"/api/neuro-commenting/campaigns/{foreign_campaign.id}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "CAMPAIGN_NOT_FOUND"


def _create_api_campaign(app_client, name: str = "API campaign") -> dict:
    create_response = app_client.post(
        "/api/neuro-commenting/campaigns",
        json={"name": name},
    )
    assert create_response.status_code == 201
    return create_response.json()


def test_api_campaign_read_and_update(app_client) -> None:
    campaign = _create_api_campaign(app_client)
    campaign_id = campaign["id"]

    list_response = app_client.get("/api/neuro-commenting/campaigns")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == campaign_id

    get_response = app_client.get(f"/api/neuro-commenting/campaigns/{campaign_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "API campaign"

    patch_response = app_client.patch(
        f"/api/neuro-commenting/campaigns/{campaign_id}",
        json={"name": "API campaign updated"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "API campaign updated"


def test_api_campaign_lifecycle_and_events(app_client) -> None:
    campaign_id = _create_api_campaign(app_client)["id"]

    start_response = app_client.post(f"/api/neuro-commenting/campaigns/{campaign_id}/start")
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    pause_response = app_client.post(f"/api/neuro-commenting/campaigns/{campaign_id}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    stop_response = app_client.post(f"/api/neuro-commenting/campaigns/{campaign_id}/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"

    events_response = app_client.get(
        "/api/neuro-commenting/events",
        params={"campaign_id": campaign_id},
    )
    assert events_response.status_code == 200
    assert events_response.json()["total"] >= 1


def test_api_campaign_accounts_and_targets_flow(app_client, db_session) -> None:
    account = seed_account(db_session, external_ref="+15550103000")
    second_account = seed_account(db_session, external_ref="+15550103001")
    db_session.commit()
    campaign_id = _create_api_campaign(app_client)["id"]

    account_response = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign_id}/accounts",
        json={"account_id": account.id, "rotation_weight": 2, "rotation_order": 1},
    )
    assert account_response.status_code == 201
    assert account_response.json()["account_id"] == account.id

    second_account_response = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign_id}/accounts",
        json={"account_id": second_account.id, "rotation_weight": 1, "rotation_order": 2},
    )
    assert second_account_response.status_code == 201

    accounts_response = app_client.get(
        f"/api/neuro-commenting/campaigns/{campaign_id}/accounts",
        params={"limit": 1},
    )
    assert accounts_response.status_code == 200
    accounts_body = accounts_response.json()
    assert accounts_body["total"] == 2
    assert accounts_body["limit"] == 1
    assert len(accounts_body["items"]) == 1
    assert accounts_body["items"][0]["account_id"] == account.id

    target_response = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign_id}/targets",
        json={"channel_ref": "@example"},
    )
    assert target_response.status_code == 201
    target_id = target_response.json()["id"]

    second_target_response = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign_id}/targets",
        json={"channel_ref": "@second-example"},
    )
    assert second_target_response.status_code == 201

    targets_response = app_client.get(
        f"/api/neuro-commenting/campaigns/{campaign_id}/targets",
        params={"limit": 1},
    )
    assert targets_response.status_code == 200
    targets_body = targets_response.json()
    assert targets_body["total"] == 2
    assert targets_body["limit"] == 1
    assert len(targets_body["items"]) == 1
    assert targets_body["items"][0]["channel_ref"] in {"@example", "@second-example"}

    delete_target_response = app_client.delete(
        f"/api/neuro-commenting/campaigns/{campaign_id}/targets/{target_id}"
    )
    assert delete_target_response.status_code == 204

    delete_account_response = app_client.delete(
        f"/api/neuro-commenting/campaigns/{campaign_id}/accounts/{account.id}"
    )
    assert delete_account_response.status_code == 204


def test_api_campaign_account_and_target_lists_are_workspace_scoped(
    app_client, db_session
) -> None:
    _own_workspace, foreign_workspace = seed_two_workspaces(db_session)
    foreign_account = seed_account(
        db_session,
        external_ref="+15550103002",
        workspace_id=foreign_workspace,
    )
    foreign_campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=foreign_workspace,
        actor_user_id="foreign-user",
        payload={"name": "Foreign campaign"},
    )
    CampaignAccountService().add_account(
        db_session,
        campaign_id=foreign_campaign.id,
        account_id=foreign_account.id,
        workspace_id=foreign_workspace,
        actor_user_id="foreign-user",
    )
    TargetService().add_target(
        db_session,
        campaign_id=foreign_campaign.id,
        workspace_id=foreign_workspace,
        actor_user_id="foreign-user",
        payload={"channel_ref": "@foreign"},
    )
    db_session.commit()

    accounts_response = app_client.get(
        f"/api/neuro-commenting/campaigns/{foreign_campaign.id}/accounts"
    )
    targets_response = app_client.get(
        f"/api/neuro-commenting/campaigns/{foreign_campaign.id}/targets"
    )

    assert accounts_response.status_code == 404
    assert accounts_response.json()["error_code"] == "CAMPAIGN_NOT_FOUND"
    assert targets_response.status_code == 404
    assert targets_response.json()["error_code"] == "CAMPAIGN_NOT_FOUND"


def test_api_generated_comment_review_flow(app_client, db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Review campaign"},
    )
    other_campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Other review campaign"},
    )
    edit_comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        generated_text="Draft text",
        final_text="Draft text",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    approve_comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        generated_text="Approved text",
        final_text="Approved text",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    reject_comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        generated_text="Rejected text",
        final_text="Rejected text",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    other_comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=other_campaign.id,
        generated_text="Other campaign text",
        final_text="Other campaign text",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    db_session.add_all([edit_comment, approve_comment, reject_comment, other_comment])
    db_session.commit()

    list_response = app_client.get("/api/neuro-commenting/generated-comments")
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 4

    filtered_response = app_client.get(
        "/api/neuro-commenting/generated-comments",
        params={"campaign_id": campaign.id},
    )
    assert filtered_response.status_code == 200
    filtered_body = filtered_response.json()
    assert filtered_body["total"] == 3
    assert {item["id"] for item in filtered_body["items"]} == {
        edit_comment.id,
        approve_comment.id,
        reject_comment.id,
    }

    get_response = app_client.get(f"/api/neuro-commenting/generated-comments/{edit_comment.id}")
    assert get_response.status_code == 200
    assert get_response.json()["generated_text"] == "Draft text"

    edit_response = app_client.patch(
        f"/api/neuro-commenting/generated-comments/{edit_comment.id}",
        json={"edited_text": "Edited text"},
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["final_text"] == "Edited text"

    approve_response = app_client.post(
        f"/api/neuro-commenting/generated-comments/{approve_comment.id}/approve"
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["approval_status"] == "approved"

    reject_response = app_client.post(
        f"/api/neuro-commenting/generated-comments/{reject_comment.id}/reject",
        json={"reason": "Not useful"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["approval_status"] == "rejected"


def test_api_generated_comment_campaign_filter_is_workspace_scoped(
    app_client, db_session
) -> None:
    _own_workspace, foreign_workspace = seed_two_workspaces(db_session)
    foreign_campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=foreign_workspace,
        actor_user_id="foreign-user",
        payload={"name": "Foreign campaign"},
    )
    db_session.add(
        NeuroCommentGeneratedComment(
            id=new_id(),
            campaign_id=foreign_campaign.id,
            generated_text="Foreign text",
            final_text="Foreign text",
            safety_status=NeuroSafetyStatus.PASSED.value,
        )
    )
    db_session.commit()

    response = app_client.get(
        "/api/neuro-commenting/generated-comments",
        params={"campaign_id": foreign_campaign.id},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "CAMPAIGN_NOT_FOUND"


def test_api_rejects_unknown_neuro_list_query_params(app_client) -> None:
    endpoints = [
        "/api/neuro-commenting/campaigns",
        "/api/neuro-commenting/generated-comments",
        "/api/neuro-commenting/events",
    ]

    for endpoint in endpoints:
        response = app_client.get(endpoint, params={"page": 1, "unexpected": "1"})

        assert response.status_code == 422
        assert response.json()["error_code"] == "HTTP_ERROR"


def test_api_create_campaign_rejects_boolean_numeric_fields(app_client) -> None:
    response = app_client.post(
        "/api/neuro-commenting/campaigns",
        json={"name": "Strict campaign", "delay_min_seconds": False},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "delay_min_seconds" for error in body["field_errors"])


def test_api_create_campaign_rejects_delay_max_below_safe_default(app_client) -> None:
    response = app_client.post(
        "/api/neuro-commenting/campaigns",
        json={"name": "Strict campaign", "delay_max_seconds": 1},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "delay_max_seconds" for error in body["field_errors"])


def test_api_create_campaign_rejects_disabled_send_strategy_at_schema_boundary(app_client) -> None:
    response = app_client.post(
        "/api/neuro-commenting/campaigns",
        json={"name": "Strict campaign", "send_strategy": "comment_as_channel"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "send_strategy" for error in body["field_errors"])


def test_api_create_campaign_rejects_numeric_auto_send_disabled_flag(app_client) -> None:
    response = app_client.post(
        "/api/neuro-commenting/campaigns",
        json={"name": "Strict campaign", "auto_send_enabled": 0},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "auto_send_enabled" for error in body["field_errors"])


def test_api_create_campaign_rejects_extra_body_fields(app_client) -> None:
    response = app_client.post(
        "/api/neuro-commenting/campaigns",
        json={"name": "Strict campaign", "unexpected": "1"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "unexpected" for error in body["field_errors"])


def test_api_create_campaign_returns_rfc3339_datetimes(app_client) -> None:
    response = app_client.post(
        "/api/neuro-commenting/campaigns",
        json={"name": "Strict campaign"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created_at"].endswith("Z") or "+" in body["created_at"]
    assert body["updated_at"].endswith("Z") or "+" in body["updated_at"]


def test_api_edit_generated_comment_requires_text_at_schema_boundary(app_client) -> None:
    response = app_client.patch(
        f"/api/neuro-commenting/generated-comments/{new_id()}",
        json={},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "edited_text" for error in body["field_errors"])
