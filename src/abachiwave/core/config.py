from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = Field(
        "development",
        validation_alias="APP_ENV",
    )
    demo_provider_name: str = Field(
        "local_deterministic_wav",
        validation_alias="DEMO_PROVIDER_NAME",
    )
    audio_to_midi_provider_name: str = Field(
        "local_monophonic_wav_to_midi",
        validation_alias="AUDIO_TO_MIDI_PROVIDER_NAME",
    )
    basic_pitch_service_url: str = Field(
        "http://basic-pitch:8080",
        validation_alias="BASIC_PITCH_SERVICE_URL",
    )
    basic_pitch_timeout_seconds: float = Field(
        90.0,
        gt=0,
        le=1800,
        validation_alias="BASIC_PITCH_TIMEOUT_SECONDS",
    )
    database_url: str = Field(
        "postgresql+asyncpg://abachiwave:abachiwave@localhost:5432/abachiwave",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field("redis://localhost:6379/0", validation_alias="REDIS_URL")
    s3_endpoint_url: str = Field("http://localhost:9000", validation_alias="S3_ENDPOINT_URL")
    s3_access_key_id: str = Field("minioadmin", validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field("minioadmin", validation_alias="S3_SECRET_ACCESS_KEY")
    s3_bucket: str = Field("abachiwave-dev", validation_alias="S3_BUCKET")
    readiness_timeout_seconds: float = Field(
        3.0,
        gt=0,
        le=30,
        validation_alias="READINESS_TIMEOUT_SECONDS",
    )
    version_write_max_retries: int = Field(
        2,
        ge=0,
        le=10,
        validation_alias="VERSION_WRITE_MAX_RETRIES",
    )
    task_timeout_seconds: int = Field(
        120,
        ge=1,
        le=3600,
        validation_alias="TASK_TIMEOUT_SECONDS",
    )
    ffmpeg_binary: str = Field("ffmpeg", validation_alias="FFMPEG_BINARY")
    ffmpeg_timeout_seconds: int = Field(
        120,
        ge=1,
        le=3600,
        validation_alias="FFMPEG_TIMEOUT_SECONDS",
    )
    text_provider_api_base_url: str | None = Field(
        None,
        validation_alias="TEXT_PROVIDER_API_BASE_URL",
    )
    text_provider_api_key: str | None = Field(
        None,
        validation_alias="TEXT_PROVIDER_API_KEY",
    )
    text_provider_model: str | None = Field(
        None,
        validation_alias="TEXT_PROVIDER_MODEL",
    )
    text_provider_timeout_seconds: float = Field(
        60.0,
        gt=0,
        le=300,
        validation_alias="TEXT_PROVIDER_TIMEOUT_SECONDS",
    )
    text_evaluation_timeout_seconds: int = Field(
        600,
        ge=30,
        le=7200,
        validation_alias="TEXT_EVALUATION_TIMEOUT_SECONDS",
    )
    max_project_uploads: int = Field(
        100,
        ge=1,
        le=1000,
        validation_alias="MAX_PROJECT_UPLOADS",
    )
    max_export_bundle_bytes: int = Field(
        512 * 1024 * 1024,
        ge=1024 * 1024,
        le=10 * 1024 * 1024 * 1024,
        validation_alias="MAX_EXPORT_BUNDLE_BYTES",
    )
    request_id_header: str = Field("X-Request-ID", validation_alias="REQUEST_ID_HEADER")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    @field_validator(
        "database_url",
        "redis_url",
        "s3_endpoint_url",
        "s3_access_key_id",
        "s3_secret_access_key",
        "s3_bucket",
        "request_id_header",
        "ffmpeg_binary",
        "audio_to_midi_provider_name",
        "basic_pitch_service_url",
    )
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def reject_default_production_storage_credentials(self) -> "Settings":
        if self.app_env == "production" and (
            self.s3_access_key_id == "minioadmin" or self.s3_secret_access_key == "minioadmin"
        ):
            raise ValueError("production requires non-default object storage credentials")
        return self

    @model_validator(mode="after")
    def require_text_provider_timeout_headroom(self) -> "Settings":
        if self.task_timeout_seconds < self.text_provider_timeout_seconds + 15:
            raise ValueError(
                "TASK_TIMEOUT_SECONDS must be at least 15 seconds greater than "
                "TEXT_PROVIDER_TIMEOUT_SECONDS"
            )
        return self

    @model_validator(mode="after")
    def require_basic_pitch_timeout_headroom(self) -> "Settings":
        if (
            self.audio_to_midi_provider_name == "spotify_basic_pitch"
            and self.task_timeout_seconds < self.basic_pitch_timeout_seconds + 15
        ):
            raise ValueError(
                "TASK_TIMEOUT_SECONDS must be at least 15 seconds greater than "
                "BASIC_PITCH_TIMEOUT_SECONDS"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
