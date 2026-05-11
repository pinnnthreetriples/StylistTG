from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any

from app.config import Settings, settings


@dataclass(frozen=True)
class TdlibRuntimeStatus:
    configured: bool
    library_configured: bool
    library_loadable: bool
    live_enabled: bool
    runtime_mode: str
    api_id_configured: bool
    api_hash_configured: bool
    readonly_smoke_available: bool
    error_code: str | None = None

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "library_configured": self.library_configured,
            "library_loadable": self.library_loadable,
            "live_enabled": self.live_enabled,
            "runtime_mode": self.runtime_mode,
            "api_id_configured": self.api_id_configured,
            "api_hash_configured": self.api_hash_configured,
            "readonly_smoke_available": self.readonly_smoke_available,
            "error_code": self.error_code,
        }


def detect_tdlib_runtime(config: Settings = settings) -> TdlibRuntimeStatus:
    library_configured = bool(config.tdlib_shared_library_path)
    live_enabled = bool(config.tdlib_live_enabled)
    api_id_configured = bool(config.telegram_api_id or config.tdlib_api_id)
    api_hash_configured = bool(config.telegram_api_hash or config.tdlib_api_hash)
    library_loadable = False
    error_code = None
    if library_configured:
        try:
            library = ctypes.CDLL(str(config.tdlib_shared_library_path))
            library_loadable = all(
                hasattr(library, symbol)
                for symbol in (
                    "td_json_client_create",
                    "td_json_client_send",
                    "td_json_client_receive",
                )
            )
            if not library_loadable:
                error_code = "tdjson_symbols_missing"
        except OSError:
            error_code = "tdjson_library_not_loadable"
    elif live_enabled:
        error_code = "tdjson_library_not_configured"

    configured = (
        library_configured and library_loadable and api_id_configured and api_hash_configured
    )
    return TdlibRuntimeStatus(
        configured=configured,
        library_configured=library_configured,
        library_loadable=library_loadable,
        live_enabled=live_enabled,
        runtime_mode=config.tdlib_runtime_mode,
        api_id_configured=api_id_configured,
        api_hash_configured=api_hash_configured,
        readonly_smoke_available=bool(
            config.tdlib_readonly_smoke_enabled and live_enabled and configured
        ),
        error_code=error_code,
    )
