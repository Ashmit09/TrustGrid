"""
Application configuration — reads from .env via pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://trustgrid_user:password@localhost:5432/trustgrid_db"
    TESTING: bool = False

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # App
    APP_ENV: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # TrustGrid constants
    INITIAL_TRUST_SCORE: int = 700
    TIME_DECAY_HALF_LIFE_DAYS: int = 90

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
