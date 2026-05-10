from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.db import Base, get_session
from app.main import app
from app.services.database import create_sqlite_test_session_factory


def test_api_contract_creates_account_asset_and_profile_job(tmp_path, monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.api.assets.STORAGE_ROOT", tmp_path / "storage")

    def override_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    try:
        account_response = client.post("/api/accounts", json={"external_ref": "primary"})
        assert account_response.status_code == 201
        account_id = account_response.json()["id"]

        image = Image.new("RGB", (64, 64), color=(255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        upload_response = client.post(
            "/api/assets/profile-photo",
            files={"file": ("profile.png", buffer.getvalue(), "image/png")},
        )
        assert upload_response.status_code == 201
        asset_id = upload_response.json()["id"]

        content_response = client.get(f"/api/assets/{asset_id}/content")
        assert content_response.status_code == 200
        assert content_response.headers["content-type"] == "image/jpeg"
        assert content_response.content

        monkeypatch.setattr("app.api.jobs.enqueue_profile_job", lambda job_id: True)

        job_response = client.post(
            "/api/jobs/profile",
            json={
                "account_id": account_id,
                "name": "Stylist TG",
                "bio": "Profile editor",
                "username": "stylist",
                "photo_asset_id": asset_id,
            },
        )
        assert job_response.status_code == 201
        assert job_response.json()["job_state"] == "queued"
        assert job_response.json()["job_id"]

        steps_response = client.get(f"/api/jobs/{job_response.json()['job_id']}/steps")
        assert steps_response.status_code == 200
        assert steps_response.json() == []
    finally:
        app.dependency_overrides.clear()
