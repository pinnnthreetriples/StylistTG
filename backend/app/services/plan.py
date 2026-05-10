from __future__ import annotations

import hashlib
import json
from typing import Any

PROFILE_STEP_TYPES = ("set_name", "set_bio", "set_username", "set_profile_photo")


def canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload.get(key) for key in ("name", "bio", "username", "photo_asset_id")}


def compute_execution_intent_hash(account_id: str, payload: dict[str, Any]) -> str:
    material: dict[str, Any] = {
        "account_id": account_id,
        "payload": canonical_payload(payload),
        "job_payload_version": 1,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_profile_plan(payload: dict[str, Any]) -> dict[str, Any]:
    name = payload.get("name") or ""
    name_parts = name.split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    step_payloads: dict[str, dict[str, Any]] = {
        "set_name": {"name": payload.get("name"), "first_name": first_name, "last_name": last_name},
        "set_bio": {"bio": payload.get("bio")},
        "set_username": {"username": payload.get("username")},
        "set_profile_photo": {
            "photo_asset_id": payload.get("photo_asset_id"),
            "asset_path": payload.get("photo_asset_path"),
        },
    }
    return {
        "plan_version": 1,
        "job_payload_version": 1,
        "steps": [
            {
                "step_key": step_type,
                "step_type": step_type,
                "order": index + 1,
                "required": True,
                "idempotency_class": "profile_field_replace",
                "payload": step_payloads[step_type],
            }
            for index, step_type in enumerate(PROFILE_STEP_TYPES)
        ],
    }
