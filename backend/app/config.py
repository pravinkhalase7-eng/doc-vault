"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "DocVault"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    secret_key: str = Field(default="dev-only-change-me", min_length=16)
    debug: bool = True

    database_url: str = "postgresql+asyncpg://docvault:docvault@localhost:5432/docvault"
    database_sync_url: str = "postgresql://docvault:docvault@localhost:5432/docvault"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    jwt_secret: str = Field(default="dev-only-jwt-secret-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    encryption_key: str = "dev-only-encryption-key-change-me"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "text-embedding-004"
    embedding_dimensions: int = 768

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = ""
    email_from_name: str = "DocVault"

    storage_root: str = "./storage/data"
    max_upload_size: int = 52_428_800
    # 100 MB per account
    default_storage_quota_bytes: int = 104_857_600

    ocr_engine: str = "tesseract"
    tesseract_cmd: str = "tesseract"

    clamav_enabled: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    trash_retention_days: int = 30

    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    guest_email: str = "guest@example.com"
    guest_password: str = "guestpass1"

    rate_limit_login: str = "5/minute"
    rate_limit_upload: str = "30/minute"
    rate_limit_ai: str = "20/minute"

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def empty_key(cls, value: str | None) -> str:
        return value or ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.email_from)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
