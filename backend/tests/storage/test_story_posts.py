from __future__ import annotations

from app.services.accounts import create_account
from app.services.story_posts import create_story_post_from_result


def test_story_post_from_tdlib_result_preserves_raw_delete_capability(db_session) -> None:
    account = create_account(db_session, external_ref="+15550102000")

    post = create_story_post_from_result(
        db_session,
        account_id=account.id,
        job_id="job-1",
        step_key="story_1_post",
        story={
            "telegram_story_id": "42",
            "media_kind": "image",
            "status": "posted",
            "raw_tdlib_json": {
                "id": 42,
                "is_posted_to_chat_page": True,
                "can_toggle_is_posted_to_chat_page": True,
            },
        },
    )

    assert post.can_be_deleted is True
