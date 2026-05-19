from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.adapters.tdlib_auth import TdlibClientFactory
from app.config import Settings, settings
from app.services.neuro_commenting.errors import NeuroRuntimeUnavailableError
from app.services.neuro_commenting.sender_service import (
    SentCommentResult,
    TelegramCommentSendError,
)
from app.services.neuro_commenting.tdlib_runtime import NeuroTdlibRuntime
from app.services.tdlib_client import safe_tdlib_error_message


class TdlibTelegramCommentSender:
    def __init__(
        self,
        *,
        config: Settings = settings,
        client_factory: TdlibClientFactory | None = None,
        runtime: NeuroTdlibRuntime | None = None,
    ) -> None:
        self._config = config
        self._runtime = runtime or NeuroTdlibRuntime(config=config, client_factory=client_factory)

    def send_comment(
        self,
        *,
        account_id: str,
        discussion_chat_id: str,
        reply_to_message_id: str,
        text: str,
    ) -> SentCommentResult:
        try:
            chat_id = _require_int_id(discussion_chat_id, error_code="CHAT_NOT_FOUND")
            reply_to_id = _require_int_id(reply_to_message_id, error_code="MESSAGE_NOT_FOUND")
            client = self._runtime.ready_client(account_id)
            response = client.send_query(
                {
                    "@type": "sendMessage",
                    "chat_id": chat_id,
                    "reply_to_message_id": reply_to_id,
                    "input_message_content": {
                        "@type": "inputMessageText",
                        "text": {"@type": "formattedText", "text": text, "entities": []},
                        "disable_web_page_preview": True,
                        "clear_draft": False,
                    },
                },
                self._config.tdlib_auth_timeout_seconds,
            )
        except TelegramCommentSendError:
            raise
        except NeuroRuntimeUnavailableError as exc:
            raise TelegramCommentSendError(exc.error_code, exc.message) from exc
        except Exception as exc:
            raise TelegramCommentSendError(
                "TDLIB_RUNTIME_UNAVAILABLE", safe_tdlib_error_message(exc)
            ) from exc
        if response.get("@type") == "error":
            raise _map_tdlib_send_error(response)
        telegram_message_id = str(response.get("id") or "")
        if not telegram_message_id:
            raise TelegramCommentSendError(
                "TDLIB_UNKNOWN_ERROR", "TDLib send returned no message id"
            )
        return SentCommentResult(
            telegram_message_id=telegram_message_id,
            sent_at=datetime.now(UTC),
        )


def _map_tdlib_send_error(response: dict[str, Any]) -> TelegramCommentSendError:
    message = str(response.get("message") or "")
    upper = message.upper()
    if "FLOOD_WAIT" in upper:
        seconds = _extract_wait_seconds(upper)
        return TelegramCommentSendError("FLOOD_WAIT", "Flood wait", flood_wait_seconds=seconds)
    if "CHAT_NOT_FOUND" in upper:
        return TelegramCommentSendError("CHAT_NOT_FOUND", "Chat not found")
    if "MESSAGE_NOT_FOUND" in upper:
        return TelegramCommentSendError("MESSAGE_NOT_FOUND", "Message not found")
    if "UNAUTHORIZED" in upper:
        return TelegramCommentSendError("TDLIB_UNAUTHORIZED", "TDLib unauthorized")
    if "RIGHT" in upper or "PERMISSION" in upper:
        return TelegramCommentSendError("PERMISSION_DENIED", "Permission denied")
    return TelegramCommentSendError("TDLIB_UNKNOWN_ERROR", safe_tdlib_error_message(response))


def _require_int_id(value: str, *, error_code: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        message = "Chat not found" if error_code == "CHAT_NOT_FOUND" else "Message not found"
        raise TelegramCommentSendError(error_code, message) from None


def _extract_wait_seconds(message: str) -> int | None:
    import re

    match = re.search(r"FLOOD_WAIT_?(\d+)", message)
    return int(match.group(1)) if match else None
