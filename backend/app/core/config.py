"""Application configuration using pydantic-settings with .env support."""

from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Auto-loads from .env file in the project root directory.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Deepgram
    DEEPGRAM_API_KEY: str = ""

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:password@localhost:5432/the-memory-host"
    )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    # SmallWebRTC
    SMALLWEBRTC_SERVER_URL: str = "http://localhost:3001"
    SMALLWEBRTC_API_KEY: str = ""

    # Bot
    BOT_NAME: str = "Memory Game Host"
    MAX_ROUNDS: int = 10
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Cache
    CACHE_ACTIVE_SESSION_TTL: int = 1800  # 30 min
    CACHE_MAX_ACTIVE_SESSIONS: int = 100
    CACHE_LEADERBOARD_TTL: int = 60  # 1 min
    CACHE_MAX_ROUNDS: int = 500
    CACHE_ROUND_TTL: int = 1800  # 30 min


settings = Settings()
