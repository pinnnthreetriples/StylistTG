import os

import pytest

from app.adapters.tdlib_auth import RealTdJsonClientFactory
from app.adapters.tdlib_profile_execution import TdlibProfileExecutionAdapter
from app.config import settings


@pytest.mark.integration
@pytest.mark.live
def test_live_tdlib_profile_execution_contract() -> None:
    account_id = os.getenv("TDLIB_TEST_ACCOUNT_ID")
    if not account_id or not os.getenv("TDLIB_API_ID") or not os.getenv("TDLIB_API_HASH"):
        pytest.skip(
            "Set TDLIB_TEST_ACCOUNT_ID, TDLIB_API_ID and TDLIB_API_HASH to run live profile tests"
        )

    adapter = TdlibProfileExecutionAdapter(
        client_factory=RealTdJsonClientFactory(settings.tdlib_shared_library_path),
        config=settings,
    )
    plan = {
        "plan_version": 1,
        "job_payload_version": 1,
        "steps": [
            {
                "step_key": "set_bio",
                "step_type": "set_bio",
                "order": 1,
                "required": True,
                "idempotency_class": "profile_field_replace",
                "payload": {"bio": os.getenv("TDLIB_TEST_BIO", "StylistTG live test")},
            }
        ],
    }

    events = list(adapter.execute(account_id, plan, {}))

    assert any(event["event"] == "step_started" for event in events)
    assert any(event["event"] in {"step_succeeded", "step_uncertain"} for event in events)
