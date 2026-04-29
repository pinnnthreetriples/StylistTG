from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.tools.live_preflight import main as preflight_main


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live smoke workflow against the local API.")
    parser.add_argument("--phone-number")
    parser.add_argument("--code")
    parser.add_argument("--photo-path")
    parser.add_argument("--account-id")
    args = parser.parse_args()

    if preflight_main() != 0:
        return 1

    client = TestClient(app)
    outcomes: dict[str, object] = {}
    if args.phone_number:
        response = client.post("/api/auth/otp/start", json={"phone_number": args.phone_number})
        outcomes["otp_start"] = response.json()
        account_id = response.json().get("account_id")
    else:
        account_id = args.account_id

    if args.code and account_id:
        response = client.post(
            "/api/auth/otp/confirm",
            json={"account_id": account_id, "code": args.code},
        )
        outcomes["otp_confirm"] = response.json()
        refresh = client.post(f"/api/accounts/{account_id}/refresh-runtime")
        outcomes["runtime_refresh"] = refresh.json()

    if args.photo_path and account_id:
        photo_bytes = Path(args.photo_path).read_bytes()
        upload = client.post(
            "/api/assets/profile-photo",
            files={"file": (Path(args.photo_path).name, photo_bytes, "image/jpeg")},
        )
        outcomes["asset_upload"] = upload.json()
        job = client.post(
            "/api/jobs/profile",
            json={
                "account_id": account_id,
                "photo_asset_id": upload.json()["id"],
            },
        )
        outcomes["profile_job"] = job.json()

    print(json.dumps(outcomes, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
