from __future__ import annotations

import pytest

from app.config import Settings
from app.models import JobState
from app.modules.account_editing import service
from app.modules.account_editing.errors import ProfileUniquenessBlockedError
from app.modules.account_editing.uniqueness_check import (
    compute_bio_similarity,
    compute_photo_similarity,
    find_similar_profiles,
)
from tests.helpers.factories import seed_account_with_profile, seed_two_workspaces


def test_bio_similarity_handles_exact_similar_and_different() -> None:
    assert compute_bio_similarity("SMM specialist, Moscow", "smm specialist, moscow") == 1.0
    assert 0.80 <= compute_bio_similarity(
        "SMM specialist, Moscow",
        "SMM specialist in Moscow",
    ) < 0.95
    assert compute_bio_similarity("SMM specialist, Moscow", "Kotlin backend engineer") < 0.8


def test_photo_similarity_uses_hamming_distance() -> None:
    assert compute_photo_similarity("0f", "0f") == 1.0
    assert compute_photo_similarity("0f", "00") == 0.5
    assert compute_photo_similarity("0f", None) == 0.0


def test_find_similar_profiles_stays_in_workspace(db_session) -> None:
    workspace_id, foreign_workspace_id = seed_two_workspaces(db_session)
    existing = seed_account_with_profile(db_session, index=1, workspace_id=workspace_id)
    foreign = seed_account_with_profile(db_session, index=2, workspace_id=foreign_workspace_id)
    existing.profile_state.bio = "SMM specialist, Moscow"
    foreign.profile_state.bio = "SMM specialist, Moscow"
    db_session.commit()

    matches = find_similar_profiles(
        db_session,
        workspace_id,
        bio="SMM specialist in Moscow",
        photo_hash=None,
        exclude_account_id=None,
    )

    assert [account.id for account in matches] == [existing.id]


def test_preview_returns_warning_for_similar_profile(db_session) -> None:
    existing = seed_account_with_profile(db_session, index=1)
    candidate = seed_account_with_profile(db_session, index=2)
    existing.profile_state.bio = "SMM specialist, Moscow"
    db_session.commit()

    preview = service.build_account_update_preview(
        db_session,
        account_id=candidate.id,
        desired_state={
            "profile": {
                "name": "Unique Candidate",
                "bio": "SMM specialist in Moscow",
                "photo_asset_id": None,
            }
        },
        workspace_id=candidate.workspace_id,
        config=Settings(profile_job_cooldown_seconds=0),
    )

    assert preview["can_create_job"] is True
    assert preview["profile_uniqueness"]["severity"] == "warning"
    assert preview["profile_uniqueness"]["similar_count"] == 1
    assert "profile_uniqueness_warning:1" in preview["warnings"]


def test_preview_blocks_exact_profile_match_without_force(db_session) -> None:
    existing = seed_account_with_profile(db_session, index=1)
    candidate = seed_account_with_profile(db_session, index=2)
    existing.profile_state.bio = "SMM specialist, Moscow"
    db_session.commit()

    preview = service.build_account_update_preview(
        db_session,
        account_id=candidate.id,
        desired_state={
            "profile": {
                "name": "Unique Candidate",
                "bio": "SMM specialist, Moscow",
                "photo_asset_id": None,
            }
        },
        workspace_id=candidate.workspace_id,
        config=Settings(profile_job_cooldown_seconds=0),
    )

    assert preview["can_create_job"] is False
    assert preview["profile_uniqueness"]["severity"] == "blocked"
    assert "profile_uniqueness_blocked:1" in preview["blocking_errors"]


def test_create_job_requires_force_for_blocking_profile_match(db_session) -> None:
    existing = seed_account_with_profile(db_session, index=1)
    candidate = seed_account_with_profile(db_session, index=2)
    existing.profile_state.bio = "SMM specialist, Moscow"
    desired_state = {
        "profile": {
            "name": "Unique Candidate",
            "bio": "SMM specialist, Moscow",
            "photo_asset_id": None,
        }
    }
    db_session.commit()

    with pytest.raises(ProfileUniquenessBlockedError):
        service.create_account_update_job(
            db_session,
            account_id=candidate.id,
            desired_state=desired_state,
            workspace_id=candidate.workspace_id,
            config=Settings(profile_job_cooldown_seconds=0),
        )

    job = service.create_account_update_job(
        db_session,
        account_id=candidate.id,
        desired_state={**desired_state, "force_profile_uniqueness": True},
        workspace_id=candidate.workspace_id,
        config=Settings(profile_job_cooldown_seconds=0),
    )

    assert job.job_state == JobState.QUEUED
