from __future__ import annotations

from dataclasses import dataclass

from app.scripts.cloud_config_check import validate_cloud_config
from app.scripts.common import CheckReport, render_report
from app.scripts.neon_smoke import run_neon_smoke
from app.scripts.object_storage_smoke import run_object_storage_smoke
from app.scripts.redis_smoke import run_redis_smoke
from app.scripts.staging_smoke import load_env_file, run_staging_smoke
from app.scripts.supabase_auth_smoke import run_supabase_auth_smoke


def _valid_cloud_env(**overrides: str) -> dict[str, str]:
    env = {
        "APP_ENV": "staging",
        "AUTH_MODE": "supabase_jwt",
        "DB_CONNECTION_MODE": "neon",
        "DATABASE_RUNTIME_URL": "postgresql+psycopg://user:db-password-value@ep-demo-pooler.us-east-1.aws.neon.tech/stylisttg?sslmode=require",
        "DATABASE_DIRECT_URL": "postgresql+psycopg://user:db-password-value@ep-demo.us-east-1.aws.neon.tech/stylisttg?sslmode=require",
        "SUPABASE_AUTH_JWKS_URL": "https://project.supabase.co/auth/v1/.well-known/jwks.json",
        "SUPABASE_AUTH_ISSUER": "https://project.supabase.co/auth/v1",
        "SUPABASE_AUTH_AUDIENCE": "authenticated",
        "STORAGE_BACKEND": "s3",
        "STORAGE_S3_ENDPOINT_URL": "https://s3.eu-central-003.backblazeb2.com",
        "STORAGE_S3_BUCKET": "stylisttg-dev-assets-pnn2026",
        "STORAGE_S3_REGION": "eu-central-003",
        "STORAGE_S3_ACCESS_KEY_ID": "access",
        "STORAGE_S3_SECRET_ACCESS_KEY": "super-sensitive-value",
        "STORAGE_S3_SIGNED_URL_EXPIRES_SECONDS": "300",
        "REDIS_URL": "rediss://default:redis-password-value@redis.example.com:6379/0",
        "TDLIB_DATABASE_ROOT": "/secure/tdlib-sessions/db",
        "TDLIB_FILES_ROOT": "/secure/tdlib-sessions/files",
        "PROFILE_EXECUTION_ADAPTER": "mock",
        "ENFORCE_LOCALHOST_ONLY": "false",
        "CORS_ORIGINS": "https://dashboard.example.com",
        "STALE_JOB_REAPER_ENABLED": "false",
        "OPERATOR_API_TOKEN": "operator-token-value",
        "PROXY_CREDENTIALS_ENCRYPTION_KEY": "uFYaczRrJN1Z__yAGnhqGrnew7Qsztc1AckpdB99XlM=",
    }
    env.update(overrides)
    return env


def _statuses(report):
    return {item.name: item.status for item in report.results}


def test_cloud_config_valid_env_passes_without_secret_leak() -> None:
    report = validate_cloud_config(_valid_cloud_env())
    rendered = str(report.to_dict())

    assert report.has_errors is False
    assert "super-sensitive-value" not in rendered
    assert "db-password-value" not in rendered
    assert "redis-password-value" not in rendered


def test_cloud_config_missing_direct_url_fails() -> None:
    env = _valid_cloud_env()
    del env["DATABASE_DIRECT_URL"]

    report = validate_cloud_config(env)

    assert _statuses(report)["database_direct_url"] == "FAIL"


def test_cloud_config_rejects_pooled_direct_url() -> None:
    report = validate_cloud_config(
        _valid_cloud_env(
            DATABASE_DIRECT_URL="postgresql+psycopg://user:secret@ep-demo-pooler.us-east-1.aws.neon.tech/stylisttg",
        )
    )

    assert _statuses(report)["database_direct_url"] == "FAIL"


def test_cloud_config_rejects_local_auth_in_cloud() -> None:
    report = validate_cloud_config(_valid_cloud_env(AUTH_MODE="local"))

    assert _statuses(report)["auth_mode"] == "FAIL"


def test_cloud_config_rejects_localhost_guard_in_cloud() -> None:
    report = validate_cloud_config(_valid_cloud_env(ENFORCE_LOCALHOST_ONLY="true"))

    assert _statuses(report)["operator_guard"] == "FAIL"


def test_cloud_config_requires_operator_token() -> None:
    report = validate_cloud_config(_valid_cloud_env(OPERATOR_API_TOKEN=""))

    assert _statuses(report)["operator_api_token"] == "FAIL"


def test_cloud_config_requires_explicit_non_wildcard_cors() -> None:
    missing = validate_cloud_config(_valid_cloud_env(CORS_ORIGINS=""))
    wildcard = validate_cloud_config(_valid_cloud_env(CORS_ORIGINS="*"))

    assert _statuses(missing)["cors_origins"] == "FAIL"
    assert _statuses(wildcard)["cors_origins"] == "FAIL"


def test_cloud_config_rejects_api_owned_stale_job_reaper() -> None:
    report = validate_cloud_config(_valid_cloud_env(STALE_JOB_REAPER_ENABLED="true"))

    assert _statuses(report)["api_stale_job_reaper"] == "FAIL"


def test_cloud_config_missing_s3_secret_fails_without_printing_secret() -> None:
    env = _valid_cloud_env()
    del env["STORAGE_S3_SECRET_ACCESS_KEY"]

    report = validate_cloud_config(env)
    rendered = str(report.to_dict())

    assert _statuses(report)["storage_s3_secret_access_key"] == "FAIL"
    assert "super-sensitive-value" not in rendered


def test_cloud_config_rejects_invalid_signed_url_ttl() -> None:
    report = validate_cloud_config(_valid_cloud_env(STORAGE_S3_SIGNED_URL_EXPIRES_SECONDS="30"))

    assert _statuses(report)["signed_url_ttl"] == "FAIL"


def test_cloud_config_requires_valid_proxy_credentials_key() -> None:
    missing = validate_cloud_config(_valid_cloud_env(PROXY_CREDENTIALS_ENCRYPTION_KEY=""))
    malformed = validate_cloud_config(_valid_cloud_env(PROXY_CREDENTIALS_ENCRYPTION_KEY="not-a-fernet-key"))

    assert _statuses(missing)["proxy_credentials_encryption_key"] == "FAIL"
    assert _statuses(malformed)["proxy_credentials_encryption_key"] == "FAIL"


def test_cloud_config_rejects_tdlib_root_under_asset_root() -> None:
    report = validate_cloud_config(
        _valid_cloud_env(
            STORAGE_LOCAL_ROOT="/secure/public-assets",
            TDLIB_DATABASE_ROOT="/secure/public-assets/tdlib/db",
        )
    )

    assert _statuses(report)["tdlib_storage_boundary"] == "FAIL"


def test_cloud_config_fails_closed_when_tdlib_live_is_enabled_without_override() -> None:
    report = validate_cloud_config(
        _valid_cloud_env(
            TDLIB_LIVE_ENABLED="true",
            PROFILE_EXECUTION_ADAPTER="tdlib",
        )
    )

    assert _statuses(report)["tdlib_live_enabled"] == "FAIL"
    assert _statuses(report)["tdlib_adapter"] == "FAIL"


def test_supabase_auth_smoke_fetches_jwks() -> None:
    report = run_supabase_auth_smoke(
        env=_valid_cloud_env(),
        fetcher=lambda _: {"keys": [{"kid": "key-1"}]},
    )

    assert _statuses(report)["jwks_keys"] == "PASS"
    assert _statuses(report)["test_jwt"] == "WARN"


def test_supabase_auth_smoke_reports_missing_keys() -> None:
    report = run_supabase_auth_smoke(env=_valid_cloud_env(), fetcher=lambda _: {"keys": []})

    assert _statuses(report)["jwks_keys"] == "FAIL"


def test_supabase_auth_smoke_reports_network_failure() -> None:
    def _raise(_url: str):
        raise OSError("network down")

    report = run_supabase_auth_smoke(env=_valid_cloud_env(), fetcher=_raise)

    assert _statuses(report)["jwks_fetch"] == "FAIL"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[str] = []

    def save_bytes(self, key: str, content: bytes, *, content_type: str | None = None):
        self.calls.append(f"save:{key}")
        self.objects[key] = content
        return type("Stored", (), {"key": key})()

    def stat(self, key: str):
        self.calls.append(f"stat:{key}")
        return type("Stat", (), {"size_bytes": len(self.objects[key])})()

    def read_bytes(self, key: str) -> bytes:
        self.calls.append(f"read:{key}")
        return self.objects[key]

    def get_signed_url(self, key: str, *, expires_seconds: int) -> str:
        self.calls.append(f"sign:{key}")
        return f"https://signed.example/{key}?X-Amz-Signature=secret"

    def delete(self, key: str) -> bool:
        self.calls.append(f"delete:{key}")
        self.objects.pop(key, None)
        return True

    def exists(self, key: str) -> bool:
        self.calls.append(f"exists:{key}")
        return key in self.objects


def test_object_storage_dry_run_makes_no_storage_calls() -> None:
    storage = FakeStorage()
    report = run_object_storage_smoke(
        env=_valid_cloud_env(),
        storage_factory=lambda _settings: storage,
    )

    assert report.has_errors is False
    assert storage.calls == []


def test_object_storage_write_mode_uses_only_smoke_prefix() -> None:
    storage = FakeStorage()
    report = run_object_storage_smoke(
        allow_write_cloud=True,
        env=_valid_cloud_env(),
        storage_factory=lambda _settings: storage,
    )

    assert report.has_errors is False
    assert storage.calls
    assert all("smoke/stylisttg/" in call for call in storage.calls)
    assert "X-Amz-Signature=secret" not in str(report.to_dict())


def test_object_storage_missing_credentials_clean_error() -> None:
    env = _valid_cloud_env()
    del env["STORAGE_S3_SECRET_ACCESS_KEY"]

    report = run_object_storage_smoke(
        allow_write_cloud=True,
        env=env,
        storage_factory=lambda _settings: FakeStorage(),
    )

    assert report.has_errors is True


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.commands: list[str] = []

    def ping(self):
        self.commands.append("ping")
        return True

    def set(self, key, value, ex=None):
        self.commands.append("set")
        self.values[key] = value

    def get(self, key):
        self.commands.append("get")
        return self.values.get(key)

    def delete(self, key):
        self.commands.append("delete")
        self.values.pop(key, None)


def test_redis_smoke_uses_only_temp_key_commands() -> None:
    fake = FakeRedis()
    report = run_redis_smoke(env=_valid_cloud_env(), client_factory=lambda _url: fake)

    assert report.has_errors is False
    assert fake.commands == ["ping", "set", "get", "delete", "get"]


def test_redis_smoke_missing_url_fails() -> None:
    env = _valid_cloud_env()
    del env["REDIS_URL"]

    report = run_redis_smoke(env=env, client_factory=lambda _url: FakeRedis())

    assert _statuses(report)["redis_url"] == "FAIL"


@dataclass
class FakeResult:
    returncode: int = 0


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _query):
        return self

    def one(self):
        return ("stylisttg", "user")


class FakeEngine:
    def connect(self):
        return FakeConnection()

    def dispose(self):
        return None


def test_neon_smoke_runtime_and_migration_checks_are_safe() -> None:
    commands = []

    def _runner(command, **kwargs):
        commands.append((command, kwargs))
        return FakeResult()

    report = run_neon_smoke(
        readonly=True,
        check_migrations=True,
        env=_valid_cloud_env(),
        engine_factory=lambda _url: FakeEngine(),
        command_runner=_runner,
    )

    assert report.has_errors is False
    assert commands[0][0] == ["python", "-m", "alembic", "current"]
    assert "secret" not in str(report.to_dict())


def test_staging_smoke_checks_health_and_ready_when_base_url_provided() -> None:
    requested_urls = []

    def _fetcher(url: str, timeout: float):
        requested_urls.append((url, timeout))
        return 200, {"status": "ok"}

    report = run_staging_smoke(
        base_url="https://staging.example.com/",
        env=_valid_cloud_env(),
        http_fetcher=_fetcher,
        cloud_config_runner=lambda env: validate_cloud_config(env),
        neon_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        supabase_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        redis_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        storage_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
    )

    assert report.has_errors is False
    assert requested_urls == [
        ("https://staging.example.com/health", 5.0),
        ("https://staging.example.com/ready", 5.0),
    ]


def test_staging_smoke_storage_write_requires_explicit_flag() -> None:
    calls = []

    def _storage_runner(**kwargs):
        calls.append(kwargs)
        return type("Report", (), {"results": []})()

    run_staging_smoke(
        include_storage=True,
        allow_write_cloud=False,
        env=_valid_cloud_env(),
        http_fetcher=None,
        cloud_config_runner=lambda env: type("Report", (), {"results": []})(),
        neon_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        supabase_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        redis_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        storage_runner=_storage_runner,
    )

    assert calls == [{"allow_write_cloud": False, "allow_production": False, "env": _valid_cloud_env()}]


def test_staging_smoke_accepts_object_storage_success_with_extra_process_env() -> None:
    storage = FakeStorage()
    env = _valid_cloud_env(ANTHROPIC_API_KEY="sk-sensitive", PATH="/bin")

    report = run_staging_smoke(
        include_storage=True,
        allow_write_cloud=True,
        env=env,
        http_fetcher=None,
        cloud_config_runner=lambda env: type("Report", (), {"results": []})(),
        neon_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        supabase_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        redis_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        storage_runner=lambda **kwargs: run_object_storage_smoke(
            **kwargs,
            storage_factory=lambda _settings: storage,
        ),
    )

    assert _statuses(report)["object_storage_write"] == "PASS"
    assert all("smoke/stylisttg/" in call for call in storage.calls)
    assert "sk-sensitive" not in render_report(report, json_output=False)


def test_staging_smoke_preserves_object_storage_failure_details() -> None:
    storage_report = CheckReport("object_storage_smoke")
    storage_report.add(
        "object_storage_write",
        "FAIL",
        "Object storage smoke failed",
        error="ClientError",
        operation="save_bytes",
        bucket="stylisttg-dev-assets-pnn2026",
    )

    report = run_staging_smoke(
        include_storage=True,
        allow_write_cloud=True,
        env=_valid_cloud_env(),
        http_fetcher=None,
        cloud_config_runner=lambda env: type("Report", (), {"results": []})(),
        neon_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        supabase_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        redis_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        storage_runner=lambda **_kwargs: storage_report,
    )

    result = next(item for item in report.results if item.name == "object_storage_write")
    assert result.status == "FAIL"
    assert result.details["error"] == "ClientError"
    assert result.details["operation"] == "save_bytes"
    assert "stylisttg-dev-assets-pnn2026" in render_report(report, json_output=False)


def test_staging_smoke_output_redacts_secrets() -> None:
    report = run_staging_smoke(
        env=_valid_cloud_env(),
        http_fetcher=None,
        cloud_config_runner=lambda env: validate_cloud_config(env),
        neon_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        supabase_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        redis_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
        storage_runner=lambda **_kwargs: type("Report", (), {"results": []})(),
    )

    rendered = str(report.to_dict())
    assert "super-sensitive-value" not in rendered
    assert "db-password-value" not in rendered
    assert "redis-password-value" not in rendered


def test_load_env_file_reads_simple_values(tmp_path) -> None:
    env_file = tmp_path / ".env.cloud.local"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "APP_ENV=staging",
                "DATABASE_URL=${DATABASE_RUNTIME_URL}",
                "DATABASE_RUNTIME_URL=postgresql://user:secret@example/db",
                "QUOTED=\"value with spaces\"",
            ]
        ),
        encoding="utf-8",
    )

    env = load_env_file(env_file)

    assert env["APP_ENV"] == "staging"
    assert env["DATABASE_URL"] == "${DATABASE_RUNTIME_URL}"
    assert env["QUOTED"] == "value with spaces"
