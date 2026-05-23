# test-analyzer: disable-file=TQA040 reason="static packaging contract tests (Dockerfile/.dockerignore/render.yaml); no runtime error paths to test"
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _final_docker_stage(dockerfile: str) -> str:
    last_stage_index = dockerfile.rfind("\nFROM ")
    if last_stage_index == -1:
        assert dockerfile.startswith("FROM ")
        return dockerfile
    return dockerfile[last_stage_index + 1 :]


def test_dockerignore_excludes_secrets_storage_and_tdlib_runtime_data() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    for pattern in (
        ".env*",
        "storage/",
        "backend/storage/",
        "tdlib/",
        "backend/tdlib/",
        "node_modules/",
        "__pycache__/",
        ".pytest_cache/",
        "dist/",
        "build/",
    ):
        assert pattern in dockerignore


def test_dockerfile_defaults_to_web_command_and_non_root_user() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim AS runtime" in dockerfile
    assert "USER stylisttg" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}" in dockerfile
    assert "rq.cli worker" not in dockerfile


def test_tdlib_dockerfile_bakes_library_but_keeps_live_disabled() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile.tdlib").read_text(encoding="utf-8")

    assert "ghcr.io/pinnnthreetriples/stylisttg-tdlib-worker:main AS tdlib-runtime" in dockerfile
    assert "COPY --from=tdlib-runtime /usr/local/lib/libtdjson.so*" in dockerfile
    assert "cmake --build build --target tdjson" not in dockerfile
    assert "git clone --depth 1 https://github.com/tdlib/td.git" not in dockerfile
    assert "TDLIB_SHARED_LIBRARY_PATH=/usr/local/lib/libtdjson.so" in dockerfile
    assert "TDLIB_LIVE_ENABLED=false" in dockerfile
    assert "PROFILE_EXECUTION_ADAPTER=mock" in dockerfile
    assert "TDLIB_READONLY_SMOKE_ENABLED=false" in dockerfile
    assert "app.scripts.tdlib_runtime_smoke --runtime-check --library-check --json" in dockerfile
    assert (
        "app.workers.run_worker --queues auth_jobs,profile_jobs,media_jobs,story_jobs" in dockerfile
    )


def test_dockerfiles_keep_uv_out_of_final_runtime_images() -> None:
    for dockerfile_name in ("Dockerfile", "Dockerfile.tdlib"):
        dockerfile = (ROOT / "backend" / dockerfile_name).read_text(encoding="utf-8")
        final_stage = _final_docker_stage(dockerfile)

        assert "FROM python:3.12-slim AS dependencies" in dockerfile
        assert "python -m pip install uv==0.10.9" in dockerfile
        assert "uv sync --locked --no-dev" in dockerfile
        assert "COPY --from=dependencies /app/.venv ./.venv" in final_stage
        assert "uv sync" not in final_stage
        assert "pip install uv" not in final_stage
        assert "uv==0.10.9" not in final_stage


def test_render_template_keeps_worker_mock_and_secrets_unsynced() -> None:
    render_yaml = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "type: web" in render_yaml
    assert "type: worker" in render_yaml
    assert "python -m app.workers.run_worker --queues profile_jobs,auth_jobs" in render_yaml
    assert "ENFORCE_LOCALHOST_ONLY" in render_yaml
    assert "CORS_ORIGINS" in render_yaml
    assert "LOG_TO_FILE" in render_yaml
    assert "PROFILE_EXECUTION_ADAPTER" in render_yaml
    assert "value: mock" in render_yaml
    assert "STORAGE_S3_SECRET_ACCESS_KEY" in render_yaml
    assert "sync: false" in render_yaml
