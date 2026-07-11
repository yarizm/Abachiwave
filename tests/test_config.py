import pytest
from pydantic import ValidationError

from abachiwave.core.config import Settings, get_settings


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6380/1")
    monkeypatch.setenv("S3_BUCKET", "abachiwave-test")
    monkeypatch.setenv("READINESS_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("VERSION_WRITE_MAX_RETRIES", "4")
    monkeypatch.setenv("TASK_TIMEOUT_SECONDS", "240")
    monkeypatch.setenv("MAX_PROJECT_UPLOADS", "12")
    monkeypatch.setenv("REQUEST_ID_HEADER", "X-Correlation-ID")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "test"
    assert settings.database_url == "sqlite+aiosqlite:///test.db"
    assert settings.redis_url == "redis://localhost:6380/1"
    assert settings.s3_bucket == "abachiwave-test"
    assert settings.readiness_timeout_seconds == 5
    assert settings.version_write_max_retries == 4
    assert settings.task_timeout_seconds == 240
    assert settings.max_project_uploads == 12
    assert settings.request_id_header == "X-Correlation-ID"
    get_settings.cache_clear()


def test_settings_reject_empty_required_values() -> None:
    with pytest.raises(ValidationError):
        Settings(S3_BUCKET="")


def test_settings_reject_default_storage_credentials_in_production() -> None:
    with pytest.raises(
        ValidationError,
        match="production requires non-default object storage credentials",
    ):
        Settings(APP_ENV="production")

    settings = Settings(
        APP_ENV="production",
        S3_ACCESS_KEY_ID="production-access",
        S3_SECRET_ACCESS_KEY="production-secret",
    )
    assert settings.app_env == "production"
