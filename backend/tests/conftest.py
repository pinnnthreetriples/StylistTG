from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("PROFILE_EXECUTION_ADAPTER", "mock")
os.environ.setdefault("STORIES_TDLIB_LIVE_ENABLED", "false")
os.environ.setdefault("QUEUE_INLINE_FALLBACK_ENABLED", "false")
os.environ.setdefault("TDLIB_API_ID", "0")
os.environ.setdefault("TDLIB_API_HASH", "")

from app.adapters.tdlib_auth import TdlibAuthResult, TdlibAuthStatus
from app.db import Base, get_session
from app.main import app
from app.models import (
    AccountState,
    Asset,
    AssetKind,
    AssetStatus,
    Job,
    JobState,
)
from app.services.plan import build_profile_plan, compute_execution_intent_hash


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with session_factory() as session:
        yield session


@pytest.fixture()
def storage_dir(tmp_path: Path) -> Path:
    return tmp_path / "storage"


# ---------------------------------------------------------------------------
# Shared fake adapters
# ---------------------------------------------------------------------------


class FakeExecutionUsableAdapter:
    """Configurable fake for execution-usable runtime checks.

    ``ok=True``  → EXECUTION_USABLE / ready
    ``ok=False`` → RUNTIME_BROKEN / broken
    ``ok=False, closed=True`` → REAUTH_REQUIRED / closed
    """

    def __init__(self, *, ok: bool = True, closed: bool = False) -> None:
        self.ok = ok
        self.closed = closed

    def inspect_runtime(self, account_id: str) -> dict:
        if self.closed:
            return {
                "ok": False,
                "account_state": AccountState.REAUTH_REQUIRED,
                "runtime_health": "closed",
                "telegram_user_id": None,
                "error": "tdlib closed",
            }
        if self.ok:
            return {
                "ok": True,
                "account_state": AccountState.EXECUTION_USABLE,
                "runtime_health": "ready",
                "telegram_user_id": "123456",
                "error": None,
            }
        return {
            "ok": False,
            "account_state": AccountState.RUNTIME_BROKEN,
            "runtime_health": "broken",
            "telegram_user_id": None,
            "error": "runtime broken",
        }


class FakeProfileSyncAdapter:
    """Fake profile sync that returns a fixed profile and records calls."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_current_profile(self, account_id: str) -> dict:
        self.calls.append(account_id)
        return {
            "telegram_user_id": "123456",
            "first_name": "King",
            "last_name": "Blackburn",
            "username": "kingblackburn",
            "bio": "Live from Telegram",
        }

    def fetch_active_stories(self, account_id: str) -> list[dict]:
        return []

    def fetch_profile_snapshot(self, account_id: str) -> dict:
        return {
            "profile": self.fetch_current_profile(account_id),
            "profile_photo": None,
            "profile_audio": None,
            "stories": [],
            "diagnostics": {},
        }

    def delete_story(self, account_id: str, story_poster_chat_id: str | None, story_id: str) -> None:
        self.calls.append(f"delete:{account_id}:{story_poster_chat_id}:{story_id}")

    def remove_story_from_profile(self, account_id: str, story_poster_chat_id: str | None, story_id: str) -> None:
        self.calls.append(f"unpost:{account_id}:{story_poster_chat_id}:{story_id}")


class FakeTdlibAuthAdapter:
    """Configurable fake for TDLib OTP auth flow.

    Override ``start_result`` / ``confirm_result`` to simulate error branches.
    """

    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []
        self.confirmed: list[tuple[str, str]] = []
        self.start_result = TdlibAuthResult(
            status=TdlibAuthStatus.WAIT_CODE,
            account_state=AccountState.AWAITING_CODE,
            runtime_health="awaiting_code",
            needs_code=True,
            session_present=True,
            recovery_marker="tdlib_wait_code",
        )
        self.confirm_result = TdlibAuthResult(
            status=TdlibAuthStatus.READY,
            account_state=AccountState.AUTHORIZED_READY,
            runtime_health="ready",
            needs_code=False,
            session_present=True,
            telegram_user_id="123456",
            recovery_marker="tdlib_ready",
        )

    def start_otp(self, account_id: str, phone_number: str) -> TdlibAuthResult:
        self.started.append((account_id, phone_number))
        return self.start_result

    def confirm_otp(self, account_id: str, code: str) -> TdlibAuthResult:
        self.confirmed.append((account_id, code))
        return self.confirm_result


# ---------------------------------------------------------------------------
# App-level test helpers
# ---------------------------------------------------------------------------


def override_app_session(session_factory) -> None:
    """Override FastAPI session dependency with a test session factory."""

    def _override():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override


def seed_asset(session: Session, *, asset_id: str = "asset-1") -> Asset:
    """Create a normalized profile photo asset for testing."""
    asset = Asset(
        id=asset_id,
        kind=AssetKind.PROFILE_PHOTO,
        source_path="assets/source/profile.png",
        normalized_path="assets/normalized/profile.jpg",
        content_hash="hash",
        mime="image/jpeg",
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def seed_audio_asset(session: Session, *, asset_id: str = "audio-1") -> Asset:
    """Create a normalized profile audio asset for testing."""
    asset = Asset(
        id=asset_id,
        kind=AssetKind.PROFILE_AUDIO,
        source_path="assets/source/audio.mp3",
        normalized_path="assets/normalized/profile-audio.mp3",
        content_hash="audio-hash",
        mime="audio/mpeg",
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def seed_story_asset(session: Session, *, asset_id: str = "story-1", kind: AssetKind = AssetKind.STORY_IMAGE) -> Asset:
    asset = Asset(
        id=asset_id,
        kind=kind,
        source_path="assets/source/story.upload",
        normalized_path="assets/normalized/story.upload",
        content_hash=f"{asset_id}-hash",
        mime="image/jpeg" if kind == AssetKind.STORY_IMAGE else "video/mp4",
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def seed_job(
    session: Session,
    *,
    account_id: str,
    payload: dict,
    state: JobState = JobState.QUEUED,
    job_id: str = "job-1",
    finished_at: datetime | None = None,
    failure_reason: str | None = None,
) -> Job:
    """Create a job row for testing."""
    job = Job(
        id=job_id,
        account_id=account_id,
        job_state=state,
        execution_intent_hash=compute_execution_intent_hash(account_id, payload),
        job_payload_version=1,
        payload_json=payload,
        plan_json_snapshot=build_profile_plan(payload),
        queued_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=finished_at,
        failure_reason=failure_reason,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
