from __future__ import annotations

from app.modules.account_onboarding.adapters.base import AccountOnboardingAdapter
from app.modules.account_onboarding.adapters.json_metadata import JsonMetadataAdapter
from app.modules.account_onboarding.adapters.phone import PhoneListAdapter
from app.modules.account_onboarding.adapters.session_file import SessionFileAdapter
from app.modules.account_onboarding.adapters.tdata import TdataArchiveAdapter
from app.modules.account_onboarding.adapters.tdlib_directory import TdlibDirectoryAdapter

_ADAPTERS: dict[str, AccountOnboardingAdapter] = {
    "phone_bulk": PhoneListAdapter(),
    "json_metadata": JsonMetadataAdapter(),
    "tdlib_directory": TdlibDirectoryAdapter(),
    "tdata_archive": TdataArchiveAdapter(),
    "session_file": SessionFileAdapter(),
}


def get_adapter(source_type: str) -> AccountOnboardingAdapter:
    return _ADAPTERS[source_type]


def adapters() -> list[AccountOnboardingAdapter]:
    return list(_ADAPTERS.values())


__all__ = ["adapters", "get_adapter"]
