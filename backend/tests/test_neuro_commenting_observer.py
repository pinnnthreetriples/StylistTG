from __future__ import annotations

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroTargetStatus,
)
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.jobs import (
    observe_campaign,
    observe_target,
    refresh_target_metadata,
)
from app.services.neuro_commenting.post_detector import PostDetector
from app.services.neuro_commenting.tdlib_observer import (
    FakeTelegramPostObserver,
    ObservedTelegramPost,
    TargetMetadata,
    TdlibTelegramPostObserver,
)
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account, seed_two_workspaces


def test_post_detector_modes_are_deterministic() -> None:
    detector = PostDetector(random_seed="seed")

    all_decision = detector.match(
        mode="all_posts", post_text=None, keywords=[], exclude_keywords=[]
    )
    keyword_decision = detector.match(
        mode="keyword_match",
        post_text="Сегодня AI и Telegram",
        keywords=["ai"],
        exclude_keywords=["spam"],
    )
    excluded_decision = detector.match(
        mode="keyword_match",
        post_text="AI spam",
        keywords=["ai"],
        exclude_keywords=["spam"],
    )
    semantic_decision = detector.match(
        mode="semantic_match", post_text="anything", keywords=[], exclude_keywords=[]
    )

    assert all_decision.matched is True
    assert keyword_decision.matched is True
    assert keyword_decision.matched_keywords == ["ai"]
    assert excluded_decision.matched is False
    assert excluded_decision.reason == "excluded_keyword"
    assert semantic_decision.matched is False
    assert semantic_decision.reason == "semantic_not_enabled"
    first_random = detector.match(
        mode="random_posts", post_text="p1", keywords=[], exclude_keywords=[]
    ).matched
    second_random = detector.match(
        mode="random_posts", post_text="p1", keywords=[], exclude_keywords=[]
    ).matched
    assert first_random in {True, False}
    assert first_random == second_random


def _campaign_with_target(db_session, *, mode: str = "all_posts"):
    account = seed_account(db_session, external_ref="+15550104001")
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Observer campaign", "mode": mode},
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
        payload={"channel_ref": "@example", "keywords": ["ai"], "exclude_keywords": ["spam"]},
    )
    db_session.commit()
    return account, campaign, target


def test_refresh_target_metadata_success(db_session) -> None:
    _account, campaign, target = _campaign_with_target(db_session)
    observer = FakeTelegramPostObserver(
        metadata=TargetMetadata(
            channel_id="channel-1",
            discussion_chat_id="discussion-1",
            title="Example",
            username="example",
            status="active",
        )
    )

    refreshed = refresh_target_metadata(
        db_session,
        campaign_id=campaign.id,
        target_id=target.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        observer=observer,
    )
    db_session.commit()

    assert refreshed.discussion_chat_id == "discussion-1"
    assert refreshed.status == NeuroTargetStatus.ACTIVE.value
    assert (
        db_session.query(NeuroCommentEvent)
        .filter_by(event_type="target_metadata_refreshed")
        .count()
        == 1
    )


def test_refresh_target_metadata_no_discussion_marks_target(db_session) -> None:
    _account, campaign, target = _campaign_with_target(db_session)
    observer = FakeTelegramPostObserver(
        metadata=TargetMetadata(
            channel_id="channel-1",
            discussion_chat_id=None,
            title="Example",
            username="example",
            status="no_discussion",
        )
    )

    refreshed = refresh_target_metadata(
        db_session,
        campaign_id=campaign.id,
        target_id=target.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        observer=observer,
    )
    db_session.commit()

    assert refreshed.status == NeuroTargetStatus.NO_DISCUSSION.value
    assert (
        db_session.query(NeuroCommentEvent).filter_by(event_type="target_no_discussion").count()
        == 1
    )


def test_tdlib_observer_resolves_channel_ref_with_public_chat_search(db_session) -> None:
    _account, _campaign, target = _campaign_with_target(db_session)
    client = _RecordingTdlibClient(
        {
            "searchPublicChat": {
                "@type": "chat",
                "id": 123,
                "title": "Example",
                "linked_chat_id": 456,
            },
            "getMe": {"@type": "user", "id": 1},
        }
    )
    observer = TdlibTelegramPostObserver(
        client_factory=_RecordingTdlibFactory(client),
        config=type(
            "Config",
            (),
            {"tdlib_receive_timeout_seconds": 1.0, "tdlib_auth_timeout_seconds": 0.1},
        )(),
    )

    metadata = observer.refresh_target_metadata("account-1", target)

    search_query = next(query for query in client.queries if query["@type"] == "searchPublicChat")
    assert search_query["username"] == "example"
    assert metadata.channel_id == "123"
    assert metadata.discussion_chat_id == "456"


def test_tdlib_observer_uses_integer_chat_ids_and_skips_missing_message_id(
    db_session,
) -> None:
    _account, _campaign, target = _campaign_with_target(db_session)
    target.channel_id = "123"
    client = _RecordingTdlibClient(
        {
            "getMe": {"@type": "user", "id": 1},
            "getChat": {"@type": "chat", "id": 123, "linked_chat_id": 456},
            "getChatHistory": {
                "@type": "messages",
                "messages": [
                    {
                        "@type": "message",
                        "chat_id": 123,
                        "id": 111,
                        "content": {
                            "@type": "messageText",
                            "text": {"@type": "formattedText", "text": "AI launch"},
                        },
                    },
                    {
                        "@type": "message",
                        "chat_id": 123,
                        "content": {"@type": "messagePhoto"},
                    },
                ],
            },
        }
    )
    observer = TdlibTelegramPostObserver(
        client_factory=_RecordingTdlibFactory(client),
        config=type(
            "Config",
            (),
            {"tdlib_receive_timeout_seconds": 1.0, "tdlib_auth_timeout_seconds": 0.1},
        )(),
    )

    posts = observer.fetch_recent_posts("account-1", target, 10)

    history_query = client.queries[-1]
    assert history_query["chat_id"] == 123
    assert len(posts) == 1
    assert posts[0].source_message_id == "111"


def test_observe_target_creates_observed_post_and_dedupes(db_session) -> None:
    _account, campaign, target = _campaign_with_target(db_session, mode="keyword_match")
    target.discussion_chat_id = "discussion-1"
    observer = FakeTelegramPostObserver(
        posts=[
            ObservedTelegramPost("chat-1", "msg-1", "AI launch", None, "en"),
            ObservedTelegramPost("chat-1", "msg-1", "AI launch duplicate", None, "en"),
            ObservedTelegramPost("chat-1", "msg-2", "AI spam", None, "en"),
        ]
    )

    posts = observe_target(
        db_session,
        campaign_id=campaign.id,
        target_id=target.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        limit=10,
        generate=False,
        observer=observer,
    )
    db_session.commit()

    assert len(posts) == 1
    assert db_session.query(NeuroCommentObservedPost).count() == 1
    assert db_session.query(NeuroCommentEvent).filter_by(event_type="post_observed").count() == 1
    assert db_session.query(NeuroCommentEvent).filter_by(event_type="post_skipped").count() >= 1


def test_observe_target_stops_after_metadata_marks_no_discussion(db_session) -> None:
    _account, campaign, target = _campaign_with_target(db_session)
    observer = FakeTelegramPostObserver(
        metadata=TargetMetadata(
            channel_id="channel-1",
            discussion_chat_id=None,
            title="Example",
            username="example",
            status="no_discussion",
        ),
        posts=[ObservedTelegramPost("chat-1", "msg-1", "AI launch", None, "en")],
    )

    posts = observe_target(
        db_session,
        campaign_id=campaign.id,
        target_id=target.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        limit=10,
        generate=True,
        observer=observer,
    )
    db_session.commit()

    assert posts == []
    assert target.status == NeuroTargetStatus.NO_DISCUSSION.value
    assert db_session.query(NeuroCommentObservedPost).count() == 0
    assert db_session.query(NeuroCommentGeneratedComment).count() == 0
    assert db_session.query(NeuroCommentEvent).filter_by(event_type="observe_failed").count() == 1


def test_observe_campaign_processes_targets_beyond_first_page(db_session) -> None:
    account, campaign, first_target = _campaign_with_target(db_session)
    first_target.discussion_chat_id = "discussion-0"
    targets = [first_target]
    for index in range(101):
        target = TargetService().add_target(
            db_session,
            campaign_id=campaign.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            actor_user_id="user-1",
            payload={
                "channel_ref": f"@example{index}",
                "discussion_chat_id": f"discussion-{index + 1}",
            },
        )
        targets.append(target)
    db_session.commit()

    class PerTargetObserver(FakeTelegramPostObserver):
        def fetch_recent_posts(self, account_id, target, limit):
            _ = (account_id, limit)
            return [ObservedTelegramPost(target.id, f"msg-{target.id}", "AI launch", None, "en")]

    posts = observe_campaign(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        limit=1,
        generate=False,
        observer=PerTargetObserver(),
    )
    db_session.commit()

    assert account.id
    assert len(posts) == len(targets)
    assert db_session.query(NeuroCommentObservedPost).count() == len(targets)


def test_foreign_workspace_cannot_observe(db_session) -> None:
    _own, foreign = seed_two_workspaces(db_session)
    _account, campaign, target = _campaign_with_target(db_session)

    try:
        observe_target(
            db_session,
            campaign_id=campaign.id,
            target_id=target.id,
            workspace_id=foreign,
            limit=10,
            generate=False,
            observer=FakeTelegramPostObserver(posts=[]),
        )
    except Exception as exc:
        assert getattr(exc, "error_code", "") == "CAMPAIGN_NOT_FOUND"
    else:
        raise AssertionError("foreign workspace observed target")


class _RecordingTdlibClient:
    def __init__(self, responses: dict[str, dict[str, object]]) -> None:
        self._responses = responses
        self.queries: list[dict[str, object]] = []

    def send_query(self, payload: dict[str, object], timeout: float) -> dict[str, object]:
        _ = timeout
        self.queries.append(payload)
        return self._responses[str(payload["@type"])]

    @property
    def client_id(self) -> int:
        return 1

    def send(self, query: dict[str, object]) -> None:
        self.queries.append(query)

    def receive(self, timeout_seconds: float) -> dict[str, object] | None:
        _ = timeout_seconds
        return None

    def close(self) -> None:
        return None


class _RecordingTdlibFactory:
    def __init__(self, client: _RecordingTdlibClient) -> None:
        self._client = client

    def create(self, account_id: str) -> _RecordingTdlibClient:
        _ = account_id
        return self._client
