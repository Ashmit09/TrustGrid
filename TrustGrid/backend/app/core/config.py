"""
TrustGrid — Application Configuration
Reads from environment variables / .env file via pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://trustgrid_user:trustgrid_pass@localhost:5432/trustgrid_db"

    # JWT
    secret_key: str = "change_me_to_a_long_random_secret_key_32_chars_plus"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # App
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # CORS
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
