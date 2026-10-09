"""Application configuration, loaded from environment / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://havoc:havoc@localhost:5432/havoc"

    # JWT
    jwt_secret: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    # Defaults
    default_project_id: str = "moon"

    # Bootstrap admin (used by scripts/seed_admin.py)
    admin_email: str = "admin@havoc.local"
    admin_password: str = "change-me-admin"
    admin_name: str = "Havoc Admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
