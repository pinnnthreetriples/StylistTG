from __future__ import annotations

from collections.abc import Iterator
import logging
import os
from pathlib import Path
import re

import app.platform_bootstrap  # noqa: F401
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("PROFILE_EXECUTION_ADAPTER", "mock")
os.environ.setdefault("STORIES_TDLIB_LIVE_ENABLED", "false")
os.environ.setdefault("QUEUE_INLINE_FALLBACK_ENABLED", "false")
os.environ.setdefault("TDLIB_API_ID", "0")
os.environ.setdefault("TDLIB_API_HASH", "")

from fastapi.testclient import TestClient

from app.adapters.tdlib_auth import TdlibAuthResult, TdlibAuthStatus
from app.db import Base, engine as app_db_engine, get_session
from app.main import app
from app.models import (
    AccountState,
    Asset,
    AssetKind,
    AssetStatus,
)
from app.services.database import dispose_sqlite_test_engines
from tests.helpers.factories import seed_job as seed_job  # noqa: F401, PLC0414  # re-export

# ---------------------------------------------------------------------------
# PII / secret leak detection (autouse)
# ---------------------------------------------------------------------------
#
# Any test that emits a high-confidence sensitive value into the log stream
# fails fast. Opt out for tests that verify redaction by intentionally feeding
# raw secrets through:
#
#     @pytest.mark.allow_pii_in_logs
#     def test_phone_is_redacted_in_journal(...): ...
#
# Patterns are deliberately CONSERVATIVE — only matches that are essentially
# always a real leak in production. False positives here should be addressed
# at the source (better redaction), not by widening the allow-list.

_SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # JWT / signed JWS: three dot-separated base64url segments where the first
    # two start with "eyJ" (base64 of '{') — the shape is highly specific.
    (
        re.compile(
            r"\beyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
        ),
        "JWT token",
    ),
    # TDLib api_hash dumped via dict/repr/log: 32 hex chars after the field name.
    # We do NOT use \b at the start because the field is often suffixed onto an
    # UPPERCASE env-var prefix like TDLIB_API_HASH=... where '_' is a word char
    # and so no boundary exists. The literal "api[_-]?hash" anchor is enough.
    (
        re.compile(
            r"(?i)api[_-]?hash[\"']?\s*[:=]\s*[\"']?[a-f0-9]{32}",
        ),
        "TDLib api_hash",
    ),
    # TDLib session string export: long base64-ish payload after the field name.
    (
        re.compile(
            r"(?i)session[_-]?string[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9+/=]{40,}",
        ),
        "TDLib session_string",
    ),
    # Authorization header with a real bearer token (not '***').
    (re.compile(r"\bAuthorization:\s*Bearer\s+[A-Za-z0-9_\-\.]{20,}"), "Bearer header"),
    # Generic password/secret/private_key field with a real-looking value.
    # Negative lookahead excludes common redaction placeholders.
    (
        re.compile(
            r"(?i)\b(password|secret|private[_-]?key)[\"']?\s*[:=]\s*[\"']?"
            r"(?!(\*+|\[REDACTED\]|<redacted>|None|null|\"\"|''))[A-Za-z0-9_\-+/=]{8,}",
        ),
        "credential field",
    ),
)


@pytest.fixture(autouse=True)
def _pii_leak_guard(
    request: pytest.FixtureRequest,
    caplog: pytest.LogCaptureFixture,
) -> Iterator[None]:
    """Fail tests that leak credentials/PII into the log stream.

    Captures records at DEBUG so any logger.debug(api_hash=...) is caught too.
    Skip with ``@pytest.mark.allow_pii_in_logs`` for tests that verify
    redaction by feeding real secrets through the SUT.
    """
    if request.node.get_closest_marker("allow_pii_in_logs") is not None:
        yield
        return

    with caplog.at_level(logging.DEBUG):
        yield

    leaks: list[str] = []
    for record in caplog.records:
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            # Malformed log call (positional args don't match format string) —
            # not our concern here.
            continue
        for pattern, label in _SENSITIVE_PATTERNS:
            if pattern.search(message):
                # Truncate evidence; never re-print full secret in the error.
                snippet = message[:80] + ("…" if len(message) > 80 else "")
                leaks.append(f"[{label}] {record.name}@{record.levelname}: {snippet}")
                break

    if leaks:
        pytest.fail(
            "Sensitive value leaked into log stream "
            "(add @pytest.mark.allow_pii_in_logs only if testing redaction):\n  - "
            + "\n  - ".join(leaks),
            pytrace=False,
        )


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
    try:
        with session_factory() as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture()
def app_client(db_session: Session) -> Iterator[TestClient]:
    """TestClient with dependency_overrides cleaned up via try/finally."""

    def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _cleanup_sqlite_test_engines() -> Iterator[None]:
    try:
        yield
    finally:
        dispose_sqlite_test_engines()
        app_db_engine.dispose()


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_teardown(item, nextitem):
    yield
    dispose_sqlite_test_engines()
    app_db_engine.dispose()


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

    def delete_story(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None:
        self.calls.append(f"delete:{account_id}:{story_poster_chat_id}:{story_id}")

    def remove_story_from_profile(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None:
        self.calls.append(f"unpost:{account_id}:{story_poster_chat_id}:{story_id}")


class FakeTdlibAuthAdapter:
    """Configurable fake for TDLib OTP auth flow.

    Override ``start_result`` / ``confirm_result`` to simulate error branches.
    """

    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []
        self.confirmed: list[tuple[str, str]] = []
        self.passwords: list[tuple[str, str]] = []
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

    def submit_password(self, account_id: str, password: str) -> TdlibAuthResult:
        self.passwords.append((account_id, password))
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


def seed_story_asset(
    session: Session, *, asset_id: str = "story-1", kind: AssetKind = AssetKind.STORY_IMAGE
) -> Asset:
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
