from __future__ import annotations

import pytest

from app.adapters.ai_profile_provider import (
    BioGenerationRequest,
    FakeAIProfileProvider,
    GeneratedBio,
)
from app.config import Settings
from app.modules.account_editing.ai_generation import (
    AIProfileGenerationError,
    AIProfileRateLimitError,
    OPERATION_TYPE,
    generate_unique_avatar,
    generate_unique_bio,
)
from app.services.operation_logs import log_operation
from tests.helpers.factories import seed_account_with_profile


class SequenceBioProvider(FakeAIProfileProvider):
    def __init__(self, values: list[str]) -> None:
        self.values = values

    def generate_bio(self, request: BioGenerationRequest) -> GeneratedBio:
        index = min(request.attempt, len(self.values) - 1)
        return GeneratedBio(text=self.values[index], provider="sequence", model="sequence-v1")


def test_generate_unique_bio_retries_until_unique(db_session) -> None:
    existing = seed_account_with_profile(db_session, index=1)
    candidate = seed_account_with_profile(db_session, index=2)
    existing.profile_state.bio = "SMM specialist, Moscow"
    db_session.commit()

    result = generate_unique_bio(
        db_session,
        candidate.workspace_id,
        account_id=candidate.id,
        language="en",
        provider=SequenceBioProvider(["SMM specialist, Moscow", "Backend engineer"]),
        config=Settings(profile_job_cooldown_seconds=0),
    )

    assert result.bio == "Backend engineer"
    assert result.attempts == 2
    assert result.uniqueness["similar_count"] == 0


def test_generate_unique_bio_exhausts_retry_budget(db_session) -> None:
    existing = seed_account_with_profile(db_session, index=1)
    candidate = seed_account_with_profile(db_session, index=2)
    existing.profile_state.bio = "SMM specialist, Moscow"
    db_session.commit()

    with pytest.raises(AIProfileGenerationError, match="2 attempts"):
        generate_unique_bio(
            db_session,
            candidate.workspace_id,
            account_id=candidate.id,
            language="en",
            provider=SequenceBioProvider(["SMM specialist, Moscow"]),
            config=Settings(ai_profile_max_attempts=2),
        )


def test_generate_unique_bio_enforces_account_daily_limit(db_session) -> None:
    account = seed_account_with_profile(db_session, index=1)
    for index in range(3):
        log_operation(
            db_session,
            account_id=account.id,
            workspace_id=account.workspace_id,
            operation_type=OPERATION_TYPE,
            operation_key=f"bio-{index}",
            status="completed",
            source="test",
            message="generated",
        )
    db_session.commit()

    with pytest.raises(AIProfileRateLimitError):
        generate_unique_bio(
            db_session,
            account.workspace_id,
            account_id=account.id,
            language="en",
            provider=SequenceBioProvider(["Unique bio"]),
            config=Settings(ai_profile_account_daily_limit=3),
        )


def test_generate_unique_avatar_returns_png_without_applying_profile(db_session) -> None:
    account = seed_account_with_profile(db_session, index=1)
    provider = FakeAIProfileProvider()

    result = generate_unique_avatar(
        db_session,
        account.workspace_id,
        account_id=account.id,
        provider=provider,
        config=Settings(),
    )

    assert result.content.startswith(b"\x89PNG")
    assert result.attempts == 1
    assert account.profile_state.profile_photo_asset_id is None
