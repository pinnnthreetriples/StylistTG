from app.services.accounts import create_account
from app.models import AccountStoryPost, utc_now
from app.services.profile_sync import (
    sync_account_live_story_posts,
    sync_account_profile_snapshot,
    sync_account_profile_state,
)

from conftest import FakeProfileSyncAdapter


def test_sync_account_profile_state_materializes_current_profile(db_session) -> None:
    account = create_account(db_session, external_ref="+15550102000", telegram_user_id="123456")
    adapter = FakeProfileSyncAdapter()

    profile_state = sync_account_profile_state(
        db_session,
        account.id,
        adapter=adapter,
    )

    assert adapter.calls == [account.id]
    assert profile_state.account_id == account.id
    assert profile_state.telegram_user_id == "123456"
    assert profile_state.first_name == "King"
    assert profile_state.last_name == "Blackburn"
    assert profile_state.username == "kingblackburn"
    assert profile_state.bio == "Live from Telegram"
    assert profile_state.synced_at is not None


def test_sync_account_profile_state_extracts_tdlib_formatted_bio(db_session) -> None:
    account = create_account(db_session, external_ref="+15550102000", telegram_user_id="123456")

    class Adapter:
        def fetch_current_profile(self, account_id: str) -> dict:
            return {
                "telegram_user_id": "123456",
                "first_name": "King",
                "last_name": "Blackburn",
                "username": "kingblackburn",
                "bio": {"@type": "formattedText", "text": "Live from Telegram", "entities": []},
            }

    profile_state = sync_account_profile_state(db_session, account.id, adapter=Adapter())

    assert profile_state.bio == "Live from Telegram"


def test_sync_account_live_story_posts_marks_missing_posts_expired(db_session) -> None:
    account = create_account(db_session, external_ref="+15550102000", telegram_user_id="123456")
    stale_post = AccountStoryPost(
        account_id=account.id,
        job_id=None,
        step_key="story_1_post",
        telegram_story_id="10",
        temporary_story_id=None,
        media_kind="image",
        asset_id=None,
        caption="old",
        privacy_preset="contacts",
        active_period_seconds=86400,
        protect_content=False,
        status="posted",
        created_at=utc_now(),
    )
    db_session.add(stale_post)
    db_session.commit()

    class Adapter:
        def fetch_current_profile(self, account_id: str) -> dict:
            return {}

        def fetch_active_stories(self, account_id: str) -> list[dict]:
            return [
                {
                    "telegram_story_id": "11",
                    "media_kind": "video",
                    "caption": "live",
                    "privacy_preset": "public",
                    "active_period_seconds": 86400,
                    "posted_at": utc_now(),
                    "expires_at": None,
                    "raw_tdlib_json": {"id": 11},
                }
            ]

    active_posts = sync_account_live_story_posts(db_session, account.id, adapter=Adapter())

    db_session.refresh(stale_post)
    assert stale_post.status == "expired"
    assert len(active_posts) == 1
    assert active_posts[0].telegram_story_id == "11"
    assert active_posts[0].status == "active"


def test_sync_account_profile_snapshot_uses_profile_page_stories(db_session) -> None:
    account = create_account(db_session, external_ref="+15550102000", telegram_user_id="123456")
    stale_post = AccountStoryPost(
        account_id=account.id,
        job_id=None,
        step_key="story_1_post",
        telegram_story_id="10",
        temporary_story_id=None,
        media_kind="image",
        asset_id=None,
        caption="old",
        privacy_preset="contacts",
        active_period_seconds=86400,
        protect_content=False,
        status="active",
        created_at=utc_now(),
    )
    db_session.add(stale_post)
    db_session.commit()

    class Adapter:
        def fetch_profile_snapshot(self, account_id: str) -> dict:
            return {
                "profile": {
                    "telegram_user_id": "123456",
                    "first_name": "King",
                    "last_name": "Blackburn",
                    "username": "kingblackburn",
                    "bio": "Live from Telegram",
                },
                "profile_photo": None,
                "profile_audio": None,
                "stories": [
                    {
                        "telegram_story_id": "2",
                        "story_poster_chat_id": "123456",
                        "media_kind": "video",
                        "caption": "first",
                        "privacy_preset": "public",
                        "active_period_seconds": 86400,
                        "can_be_deleted": True,
                        "posted_at": utc_now(),
                        "expires_at": None,
                        "raw_tdlib_json": {"id": 2},
                    },
                    {
                        "telegram_story_id": "1",
                        "media_kind": "video",
                        "caption": "second",
                        "privacy_preset": "public",
                        "active_period_seconds": 86400,
                        "posted_at": utc_now(),
                        "expires_at": None,
                        "raw_tdlib_json": {"id": 1},
                    },
                ],
                "diagnostics": {"profile_page_story_count": 2, "active_story_count": 1},
            }

    result = sync_account_profile_snapshot(db_session, account.id, adapter=Adapter())

    db_session.refresh(stale_post)
    assert stale_post.status == "expired"
    assert result["profile_state"].profile_photo_asset_id is None
    assert [post.telegram_story_id for post in result["story_posts"]] == ["2", "1"]
    assert result["story_posts"][0].story_poster_chat_id == "123456"
    assert result["story_posts"][0].can_be_deleted is True
