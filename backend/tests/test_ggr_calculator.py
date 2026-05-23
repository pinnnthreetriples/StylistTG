"""Tests for GGR (GramGPT Rating) Calculator — Phase 2 Task 11."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    Account,
    AccountProfileState,
    AccountProxy,
    AccountRuntimeState,
    AccountState,
    AccountStatusObservation,
    User,
    WarmupSession,
    WarmupStrategy,
    Workspace,
    WorkspaceMember,
    new_id,
    DEFAULT_LOCAL_WORKSPACE_ID,
)
from app.services.ggr_calculator import (
    RECALC_INTERVAL,
    _age_score,
    _apply_smoothing,
    _fingerprint_score,
    _origin_score,
    _history_score,
    _ip_change_score,
    _profile_score,
    _proxy_score,
    _session_anomaly_score,
    _warmup_score,
    backfill_ggr_scores,
    calculate_ggr,
    compute_bucket,
    compute_score,
    get_ggr_score,
)

pytestmark = [pytest.mark.unit]

_NOW = datetime(2026, 5, 20, 0, 0, 0, tzinfo=UTC)
_ALL_COMPONENTS = [
    "age",
    "origin",
    "history",
    "proxy",
    "fingerprint",
    "ip_change",
    "session_anomaly",
    "warmup",
    "profile",
]


def _make_workspace(
    session: Session, *, name: str = "Test Workspace", ws_id: str | None = None
) -> Workspace:
    """Create a workspace with required fields (slug, owner)."""
    wid = ws_id or new_id()
    user = User(
        id=new_id(),
        email=f"user-{wid[:8]}@test.local",
        external_auth_provider="test",
        external_auth_user_id=f"ext-{wid[:8]}",
    )
    session.add(user)
    session.flush()
    ws = Workspace(id=wid, name=name, slug=f"ws-{wid[:8]}", owner_user_id=user.id)
    session.add(ws)
    session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    session.commit()
    return ws


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as sess:
        yield sess
    engine.dispose()


@pytest.fixture()
def workspace(session: Session) -> Workspace:
    return _make_workspace(session, ws_id=DEFAULT_LOCAL_WORKSPACE_ID)


def _make_account(
    session: Session,
    workspace_id: str,
    *,
    external_ref: str = "+7999000001",
    created_at: datetime | None = None,
    account_state: str = AccountState.AUTHORIZED_READY,
) -> Account:
    acct = Account(
        id=new_id(),
        workspace_id=workspace_id,
        external_ref=external_ref,
        account_state=account_state,
        created_at=created_at or (_NOW - timedelta(days=45)),
    )
    acct.runtime_state = AccountRuntimeState(
        session_present=False,
        runtime_health="unknown",
        reauth_required=False,
    )
    session.add(acct)
    session.commit()
    return acct


def _add_observation(
    session: Session,
    account: Account,
    *,
    observed_at: datetime = _NOW,
    device_model_hash: str | None = None,
    proxy_ip_hash: str | None = None,
    consecutive_failures: int = 0,
    workspace_id: str | None = None,
) -> None:
    session.add(
        AccountStatusObservation(
            workspace_id=workspace_id or account.workspace_id,
            account_id=account.id,
            observed_at=observed_at,
            proxy_healthy=True,
            proxy_ip_hash=proxy_ip_hash,
            tdlib_authorized=True,
            device_model_hash=device_model_hash,
            consecutive_failures=consecutive_failures,
            auto_action_taken="none",
            details_json={},
        )
    )
    session.commit()


@pytest.fixture()
def account(session: Session, workspace: Workspace) -> Account:
    return _make_account(session, workspace.id)


# ---------------------------------------------------------------------------
# 1. Bucket boundaries
# ---------------------------------------------------------------------------


class TestBucketBoundaries:
    def test_weak_upper_bound(self):
        assert compute_bucket(3.99) == "weak"

    def test_medium_lower_bound(self):
        assert compute_bucket(4.0) == "medium"

    def test_medium_upper_bound(self):
        assert compute_bucket(6.99) == "medium"

    def test_strong_lower_bound(self):
        assert compute_bucket(7.0) == "strong"

    def test_max_score(self):
        assert compute_bucket(10.0) == "strong"

    def test_min_score(self):
        assert compute_bucket(1.0) == "weak"


# ---------------------------------------------------------------------------
# 2. Isolated component scoring
# ---------------------------------------------------------------------------


@freeze_time(_NOW)
class TestComponentScoring:
    def test_age_score_new_account(self, session: Session, workspace: Workspace):
        acct = _make_account(
            session,
            workspace.id,
            external_ref="+7999000010",
            created_at=_NOW - timedelta(hours=12),
            account_state=AccountState.REGISTERED,
        )
        assert _age_score(acct) == 0.0

    def test_age_score_one_week(self, session: Session, workspace: Workspace):
        acct = _make_account(
            session,
            workspace.id,
            external_ref="+7999000011",
            created_at=_NOW - timedelta(days=3),
            account_state=AccountState.REGISTERED,
        )
        assert _age_score(acct) == 0.5

    def test_age_score_month(self, session: Session, workspace: Workspace):
        acct = _make_account(
            session,
            workspace.id,
            external_ref="+7999000012",
            created_at=_NOW - timedelta(days=15),
            account_state=AccountState.REGISTERED,
        )
        assert _age_score(acct) == 0.8

    def test_age_score_old(self, session: Session, workspace: Workspace):
        acct = _make_account(
            session,
            workspace.id,
            external_ref="+7999000013",
            created_at=_NOW - timedelta(days=60),
            account_state=AccountState.REGISTERED,
        )
        assert _age_score(acct) == 1.0

    @pytest.mark.parametrize(
        ("origin", "expected"),
        [
            ("created", 1.0),
            ("imported", 0.7),
            ("bought", 0.4),
            ("legacy", 0.7),
        ],
    )
    def test_origin_score_maps_account_origin(
        self, session: Session, workspace: Workspace, origin: str, expected: float
    ):
        acct = _make_account(session, workspace.id, external_ref=f"+7999000014-{origin}")
        acct.origin = origin
        assert _origin_score(session, acct) == expected

    def test_history_score_hardcoded(self, session: Session, workspace: Workspace):
        acct = _make_account(session, workspace.id, external_ref="+7999000015")
        assert _history_score(session, acct) == 1.0

    @pytest.mark.parametrize(
        ("hashes", "expected"),
        [
            ([], 0.5),
            (["device-a"], 1.0),
            (["device-a", "device-b"], 0.6),
            (["device-a", "device-b", "device-c"], 0.2),
        ],
    )
    def test_fingerprint_score_counts_distinct_recent_device_hashes(
        self, session: Session, workspace: Workspace, hashes: list[str], expected: float
    ):
        acct = _make_account(session, workspace.id, external_ref=f"+799900010{len(hashes)}")
        for device_hash in hashes:
            _add_observation(session, acct, device_model_hash=device_hash)

        assert _fingerprint_score(session, acct) == expected

    @pytest.mark.parametrize(
        ("hashes", "expected"),
        [
            ([], 0.5),
            (["ip-a"], 1.0),
            (["ip-a", "ip-b"], 0.7),
            (["ip-a", "ip-b", "ip-c"], 0.4),
            (["ip-a", "ip-b", "ip-c", "ip-d"], 0.1),
        ],
    )
    def test_ip_change_score_counts_distinct_recent_proxy_hashes(
        self, session: Session, workspace: Workspace, hashes: list[str], expected: float
    ):
        acct = _make_account(session, workspace.id, external_ref=f"+799900011{len(hashes)}")
        for proxy_hash in hashes:
            _add_observation(session, acct, proxy_ip_hash=proxy_hash)

        assert _ip_change_score(session, acct) == expected

    @pytest.mark.parametrize(
        ("failures", "expected"),
        [
            (None, 0.5),
            (0, 1.0),
            (2, 0.7),
            (4, 0.4),
            (5, 0.1),
        ],
    )
    def test_session_anomaly_score_uses_latest_consecutive_failures(
        self, session: Session, workspace: Workspace, failures: int | None, expected: float
    ):
        acct = _make_account(session, workspace.id, external_ref=f"+799900012{failures}")
        if failures is not None:
            _add_observation(
                session,
                acct,
                observed_at=_NOW - timedelta(hours=1),
                consecutive_failures=0,
            )
            _add_observation(session, acct, consecutive_failures=failures)

        assert _session_anomaly_score(session, acct) == expected

    def test_status_observation_scores_are_workspace_scoped(
        self, session: Session, workspace: Workspace
    ):
        acct = _make_account(session, workspace.id, external_ref="+7999000129")
        foreign_workspace = _make_workspace(session, name="Foreign")
        _add_observation(
            session,
            acct,
            device_model_hash="foreign",
            proxy_ip_hash="foreign",
            consecutive_failures=5,
            workspace_id=foreign_workspace.id,
        )

        actual = {
            "fingerprint": _fingerprint_score(session, acct),
            "ip_change": _ip_change_score(session, acct),
            "session_anomaly": _session_anomaly_score(session, acct),
        }
        assert actual == {"fingerprint": 0.5, "ip_change": 0.5, "session_anomaly": 0.5}


# ---------------------------------------------------------------------------
# 2b. Integration component scoring (reads from real DB tables)
# ---------------------------------------------------------------------------


@freeze_time(_NOW)
class TestComponentScoringIntegration:
    def test_proxy_score_reads_from_proxy_table(self, session: Session, workspace: Workspace):
        acct = _make_account(session, workspace.id, external_ref="+7999000030")
        proxy = AccountProxy(
            account_id=acct.id,
            proxy_type="socks5",
            host="1.2.3.4",
            port=1080,
            status="tcp_working",
        )
        session.add(proxy)
        session.commit()
        assert _proxy_score(session, acct) == 1.0

        proxy.status = "failed"
        session.commit()
        assert _proxy_score(session, acct) == 0.0

        proxy.status = "unknown"
        session.commit()
        assert _proxy_score(session, acct) == 0.5

    def test_proxy_score_no_proxy(self, session: Session, workspace: Workspace):
        acct = _make_account(session, workspace.id, external_ref="+7999000031")
        assert _proxy_score(session, acct) == 0.5

    def test_warmup_score_reads_from_warmup_session(self, session: Session, workspace: Workspace):
        acct = _make_account(session, workspace.id, external_ref="+7999000032")
        strategy = WarmupStrategy(
            id=new_id(),
            workspace_id=workspace.id,
            name="test-strategy",
            execution_mode="passive",
        )
        session.add(strategy)
        session.flush()
        ws = WarmupSession(
            id=new_id(),
            workspace_id=workspace.id,
            account_id=acct.id,
            strategy_id=strategy.id,
            status="completed",
            current_day=0,
            duration_days=7,
            cadence_hours=6,
        )
        session.add(ws)
        session.commit()
        assert _warmup_score(session, acct) == 1.0

        ws.status = "active"
        session.commit()
        assert _warmup_score(session, acct) == 0.5

    def test_warmup_score_no_session(self, session: Session, workspace: Workspace):
        acct = _make_account(session, workspace.id, external_ref="+7999000033")
        assert _warmup_score(session, acct) == 0.0

    def test_profile_score_reads_from_account_profile_state(
        self, session: Session, workspace: Workspace
    ):
        acct = _make_account(session, workspace.id, external_ref="+7999000034")
        ps = AccountProfileState(
            account_id=acct.id,
            first_name="X",
            bio="hello",
            profile_photo_asset_id="abc",
        )
        session.add(ps)
        session.commit()
        assert _profile_score(session, acct) == 0.75

    def test_profile_score_empty(self, session: Session, workspace: Workspace):
        acct = _make_account(session, workspace.id, external_ref="+7999000035")
        assert _profile_score(session, acct) == 0.0


# ---------------------------------------------------------------------------
# 3. Total score formula verification
# ---------------------------------------------------------------------------


class TestScoreFormula:
    def test_all_components_max(self):
        components = {k: 1.0 for k in _ALL_COMPONENTS}
        score = compute_score(components)
        expected = round(1.0 + 9.0 * 1.0, 1)
        assert score == expected == 10.0

    def test_all_components_zero(self):
        components = {k: 0.0 for k in _ALL_COMPONENTS}
        score = compute_score(components)
        expected = round(1.0 + 9.0 * 0.0, 1)
        assert score == expected == 1.0

    def test_mixed_components(self):
        components = {
            "age": 1.0,  # 0.20 * 1.0 = 0.20
            "origin": 0.7,  # 0.10 * 0.7 = 0.07
            "history": 0.8,  # 0.15 * 0.8 = 0.12
            "proxy": 1.0,  # 0.15 * 1.0 = 0.15
            "fingerprint": 0.5,  # 0.10 * 0.5 = 0.05
            "ip_change": 1.0,  # 0.10 * 1.0 = 0.10
            "session_anomaly": 1.0,  # 0.10 * 1.0 = 0.10
            "warmup": 0.5,  # 0.05 * 0.5 = 0.025
            "profile": 0.667,  # 0.05 * 0.667 = 0.03335
        }
        total = sum(
            {
                "age": 0.20,
                "origin": 0.10,
                "history": 0.15,
                "proxy": 0.15,
                "fingerprint": 0.10,
                "ip_change": 0.10,
                "session_anomaly": 0.10,
                "warmup": 0.05,
                "profile": 0.05,
            }[k]
            * v
            for k, v in components.items()
        )
        expected = round(1.0 + 9.0 * total, 1)
        score = compute_score(components)
        assert score == expected


# ---------------------------------------------------------------------------
# 4. Backfill for existing accounts
# ---------------------------------------------------------------------------


class TestBackfill:
    def test_backfill_creates_default_records(
        self, session: Session, workspace: Workspace, account: Account
    ):
        count = backfill_ggr_scores(session, workspace.id)
        assert count == 1
        ggr = get_ggr_score(session, account.id, workspace.id)
        assert ggr is not None
        assert ggr.score == 5.0
        assert ggr.bucket == "medium"

    def test_backfill_skips_existing(
        self, session: Session, workspace: Workspace, account: Account
    ):
        backfill_ggr_scores(session, workspace.id)
        count = backfill_ggr_scores(session, workspace.id)
        assert count == 0


# ---------------------------------------------------------------------------
# 5. Recalc on demand sets next_calculation_at + 6h
# ---------------------------------------------------------------------------


class TestRecalcOnDemand:
    def test_recalc_sets_next_calculation(
        self, session: Session, workspace: Workspace, account: Account
    ):
        ggr = calculate_ggr(session, account, workspace.id)
        session.commit()
        assert ggr.next_calculation_at is not None
        assert ggr.last_calculated_at is not None
        expected_next = ggr.last_calculated_at + RECALC_INTERVAL
        diff = abs((ggr.next_calculation_at - expected_next).total_seconds())
        assert diff < 1.0

    def test_calculate_ggr_query_budget_includes_observation_inputs(
        self, session: Session, workspace: Workspace
    ):
        acct = _make_account(session, workspace.id, external_ref="+7999000040")
        session.add(
            AccountProxy(
                account_id=acct.id,
                proxy_type="socks5",
                host="1.2.3.4",
                port=1080,
                status="tcp_working",
            )
        )
        session.add(
            AccountProfileState(
                account_id=acct.id,
                first_name="X",
                bio="hello",
                profile_photo_asset_id="abc",
            )
        )
        strategy = WarmupStrategy(
            id=new_id(),
            workspace_id=workspace.id,
            name="query-budget-strategy",
            execution_mode="passive",
        )
        session.add(strategy)
        session.flush()
        session.add(
            WarmupSession(
                id=new_id(),
                workspace_id=workspace.id,
                account_id=acct.id,
                strategy_id=strategy.id,
                status="completed",
                current_day=0,
                duration_days=7,
                cadence_hours=6,
            )
        )
        _add_observation(
            session,
            acct,
            device_model_hash="device-a",
            proxy_ip_hash="ip-a",
            consecutive_failures=0,
        )

        statements: list[str] = []
        engine = session.get_bind()

        def _track_statement(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _track_statement)
        try:
            calculate_ggr(session, acct, workspace.id, force=True)
        finally:
            event.remove(engine, "before_cursor_execute", _track_statement)

        assert len(statements) <= 9


# ---------------------------------------------------------------------------
# 6. Smoothing: max delta 1.0 per cycle
# ---------------------------------------------------------------------------


class TestSmoothing:
    def test_no_previous_score(self):
        assert _apply_smoothing(8.5, None) == 8.5

    def test_small_increase(self):
        assert _apply_smoothing(5.5, 5.0) == 5.5

    def test_large_increase_clamped(self):
        result = _apply_smoothing(8.0, 5.0)
        assert result == 6.0

    def test_large_decrease_clamped(self):
        result = _apply_smoothing(3.0, 6.0)
        assert result == 5.0

    def test_exact_boundary(self):
        assert _apply_smoothing(6.0, 5.0) == 6.0
        assert _apply_smoothing(4.0, 5.0) == 4.0


# ---------------------------------------------------------------------------
# 7. Tenant isolation
# ---------------------------------------------------------------------------


@freeze_time(_NOW)
class TestTenantIsolation:
    def test_workspace_a_cannot_see_workspace_b(self, session: Session):
        ws_a = _make_workspace(session, name="Workspace A")
        ws_b = _make_workspace(session, name="Workspace B")

        acct_a = _make_account(
            session,
            ws_a.id,
            external_ref="+7999000020",
            created_at=_NOW - timedelta(days=30),
        )
        acct_b = _make_account(
            session,
            ws_b.id,
            external_ref="+7999000021",
            created_at=_NOW - timedelta(days=30),
        )

        calculate_ggr(session, acct_a, ws_a.id)
        calculate_ggr(session, acct_b, ws_b.id)
        session.commit()

        # Workspace A cannot see workspace B's score
        ggr_b_from_a = get_ggr_score(session, acct_b.id, ws_a.id)
        assert ggr_b_from_a is None

        # Workspace B cannot see workspace A's score
        ggr_a_from_b = get_ggr_score(session, acct_a.id, ws_b.id)
        assert ggr_a_from_b is None

        # Each workspace sees its own score
        assert get_ggr_score(session, acct_a.id, ws_a.id) is not None
        assert get_ggr_score(session, acct_b.id, ws_b.id) is not None
