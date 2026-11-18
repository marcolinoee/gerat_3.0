"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "GERAT Web API"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "postgresql+asyncpg://gerat:gerat@db:5432/gerat"

    JWT_SECRET_KEY: str = "change-me-in-production-super-secret-key-32bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    REFRESH_COOKIE_NAME: str = "gerat_refresh_token"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"

    SEED_ADMIN_EMAIL: str = "professor@gerat.local"
    SEED_ADMIN_NAME: str = "Prof. Dr. Coordenador GERAT"
    SEED_ADMIN_PASSWORD: str | None = None

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8080"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
