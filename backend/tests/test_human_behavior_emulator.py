"""Unit tests for the HumanBehaviorEmulator (Phase 2 Task 14).

6 test cases covering:
1. baseline created once, repeated get returns the same
2. randomize_for_session within ±10%
3. typing_emulator duration ≈ len(text)*60/cpm ± 15%
4. typo_generator probability=0.0 → never, 1.0 → always
5. decoy_actions probability=0.0 → none, 1.0 → always
6. action_sequencer determinism
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.db import Base
from app.models import Account, new_id
from app.modules.warmup.circadian import generate_personality_seed
from app.services.database import create_sqlite_test_session_factory
from app.services.human_behavior.action_sequencer import shuffle
from app.services.human_behavior.behavior_profile import (
    get_or_create_baseline,
    randomize_for_session,
)
from app.services.human_behavior.decoy_actions import run_before_send
from app.services.human_behavior.typing_emulator import emit_typing
from app.services.human_behavior.typo_generator import maybe_typo
from app.services.workspace_safety_policy import create_workspace_safety_policy


WORKSPACE_ID = "00000000-0000-4000-8000-000000000002"


def _seeded_rng(seed: int = 42) -> random.Random:
    """Return a deterministic RNG instance (seed is explicit)."""
    return random.Random(seed)


def _make_session() -> Session:
    factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    return factory()


def _ensure_account(session: Session, account_id: str | None = None) -> Account:
    """Create a minimal account row for FK satisfaction."""
    from app.services.workspaces import ensure_default_workspace

    ensure_default_workspace(session)
    aid = account_id or new_id()
    account = Account(id=aid, workspace_id=WORKSPACE_ID, external_ref=f"+7999{aid[:4]}")
    session.add(account)
    session.flush()
    return account


class TestBehaviorProfileBaseline:
    """1. baseline created once; repeated get returns the same."""

    def test_get_or_create_returns_same_on_second_call(self):
        session = _make_session()
        account = _ensure_account(session)

        first = get_or_create_baseline(session, account.id, WORKSPACE_ID, preset="balanced")
        session.flush()
        second = get_or_create_baseline(session, account.id, WORKSPACE_ID, preset="balanced")
        assert first.id == second.id
        assert first.typing_speed_baseline_cpm == second.typing_speed_baseline_cpm
        assert first.typo_rate_baseline == second.typo_rate_baseline


class TestRandomizeForSession:
    """2. randomize_for_session returns values within ±10% of baseline."""

    def test_session_values_within_10_percent(self):
        session = _make_session()
        account = _ensure_account(session)
        baseline = get_or_create_baseline(session, account.id, WORKSPACE_ID, rng=_seeded_rng(42))

        rng = _seeded_rng(99)
        sp = randomize_for_session(baseline, rng=rng)

        if baseline.typing_speed_baseline_cpm is not None:
            lo = baseline.typing_speed_baseline_cpm * 0.9
            hi = baseline.typing_speed_baseline_cpm * 1.1
            assert lo <= sp.typing_speed_cpm <= hi
        else:
            assert sp.typing_speed_cpm is None

        # typo rate
        lo_t = baseline.typo_rate_baseline * 0.9
        hi_t = baseline.typo_rate_baseline * 1.1
        assert lo_t <= sp.typo_rate <= hi_t or sp.typo_rate == 0.0


class TestBaselineFromPersonalitySeed:
    """2b. get_or_create_baseline uses per-account personality, not policy behavior."""

    def test_personality_seed_derives_typing_range(self):
        session = _make_session()
        account = _ensure_account(session, account_id="personality-seed-account")

        baseline = get_or_create_baseline(session, account.id, WORKSPACE_ID, rng=_seeded_rng(42))
        expected_cpm = generate_personality_seed(account.id)["typing_speed_cps"] * 60.0
        assert baseline.typing_speed_baseline_cpm is not None
        assert expected_cpm * 0.95 <= baseline.typing_speed_baseline_cpm <= expected_cpm * 1.05

    def test_workspace_policy_does_not_change_personality_baseline(self):
        session = _make_session()
        account = _ensure_account(session, account_id="policy-ignored-account")
        create_workspace_safety_policy(session, workspace_id=WORKSPACE_ID, mode="conservative")
        session.commit()

        conservative_baseline = get_or_create_baseline(
            session, account.id, WORKSPACE_ID, rng=_seeded_rng(42)
        )

        other_session = _make_session()
        same_account = _ensure_account(other_session, account_id=account.id)
        create_workspace_safety_policy(other_session, workspace_id=WORKSPACE_ID, mode="aggressive")
        other_session.commit()
        aggressive_policy_baseline = get_or_create_baseline(
            other_session, same_account.id, WORKSPACE_ID, rng=_seeded_rng(42)
        )

        assert conservative_baseline.typing_speed_baseline_cpm == (
            aggressive_policy_baseline.typing_speed_baseline_cpm
        )
        assert conservative_baseline.typo_rate_baseline == aggressive_policy_baseline.typo_rate_baseline

    def test_permissive_legacy_preset_keeps_personality_typing(self):
        session = _make_session()
        account = _ensure_account(session, account_id="legacy-permissive-account")

        baseline = get_or_create_baseline(
            session, account.id, WORKSPACE_ID, preset="aggressive", rng=_seeded_rng(42)
        )
        assert baseline.typing_speed_baseline_cpm is not None
        sp = randomize_for_session(baseline, rng=_seeded_rng(99))
        assert sp.typing_speed_cpm is not None


class TestTypingEmulator:
    """3. typing_emulator duration ≈ len(text)*60/cpm ± 15%."""

    def test_duration_approximately_correct(self):
        text = "Hello world, this is a test of the typing emulator"
        cpm = 120.0
        fragments = emit_typing(text, cpm, rng=_seeded_rng(42))

        expected = len(text) * 60.0 / cpm
        actual_typing_only = sum(f.duration_seconds for f in fragments)

        # The typing-only duration (excluding pauses) should be ≈ expected ± 15%
        assert abs(actual_typing_only - expected) / expected < 0.15

    def test_empty_text_returns_no_fragments(self):
        assert emit_typing("", 120.0) == []


class TestTypoGenerator:
    """4. probability=0.0 → never typo; 1.0 → always."""

    def test_zero_probability_never_typos(self):
        rng = _seeded_rng(42)
        for _ in range(100):
            result = maybe_typo("Hello world", 0.0, rng=rng)
            assert result.has_typo is False

    def test_full_probability_always_typos(self):
        rng = _seeded_rng(42)
        for _ in range(100):
            result = maybe_typo("Hello world", 1.0, rng=rng)
            assert result.has_typo is True
            assert result.typo_text is not None
            assert 0.2 <= result.correction_delay_seconds <= 0.8


class TestDecoyActions:
    """5. probability=0.0 → no decoys; 1.0 → always."""

    def test_zero_probability_no_actions(self):
        rng = _seeded_rng(42)
        for _ in range(100):
            actions = run_before_send("acct-1", 0.0, rng=rng)
            assert actions == []

    def test_full_probability_always_actions(self):
        rng = _seeded_rng(42)
        for _ in range(100):
            actions = run_before_send("acct-1", 1.0, rng=rng)
            assert len(actions) >= 1
            for a in actions:
                assert a.kind in ("getUser", "getChat")


class TestActionSequencer:
    """6. shuffle(seed=X) is deterministic; different seeds → different order."""

    def test_same_seed_same_order(self):
        items = list(range(20))
        a = shuffle(items, seed=42)
        b = shuffle(items, seed=42)
        assert a == b

    def test_different_seed_different_order(self):
        items = list(range(20))
        a = shuffle(items, seed=42)
        b = shuffle(items, seed=99)
        # With 20 items, different seeds should produce different orders
        assert a != b
