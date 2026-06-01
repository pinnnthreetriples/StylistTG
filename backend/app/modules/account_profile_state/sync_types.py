from __future__ import annotations

from typing import Any, Protocol, TypeAlias

JsonDict: TypeAlias = dict[str, Any]
JsonList: TypeAlias = list[JsonDict]


class ProfileSyncAdapter(Protocol):
    def fetch_profile_snapshot(self, account_id: str) -> JsonDict: ...
    def fetch_current_profile(self, account_id: str) -> JsonDict: ...
    def fetch_active_stories(self, account_id: str) -> JsonList: ...
    def delete_story(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None: ...
    def remove_story_from_profile(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None: ...
