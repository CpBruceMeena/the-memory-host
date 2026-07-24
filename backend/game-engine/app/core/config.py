"""Application configuration for The Memory Host — Game Engine Service."""

from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Game Engine settings loaded from environment variables.

    The .env file is at the project root (parent of backend/).
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Deepgram (required for STT/TTS)
    DEEPGRAM_API_KEY: str = ""

    # Database (shared with rest-api service)
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:password@localhost:5432/the-memory-host"
    )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    # Signaling server (WebRTC)
    SMALLWEBRTC_SERVER_URL: str = "ws://localhost:3001"

    # Bot
    BOT_NAME: str = "Memory Game Host"
    MAX_ROUNDS: int = 10
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 3002  # HTTP endpoint for start-session

    # Cache (local in-memory, not shared with rest-api)
    CACHE_ACTIVE_SESSION_TTL: int = 1800  # 30 min
    CACHE_MAX_ACTIVE_SESSIONS: int = 100
    CACHE_LEADERBOARD_TTL: int = 60  # 1 min
    CACHE_MAX_ROUNDS: int = 500
    CACHE_ROUND_TTL: int = 1800  # 30 min


settings = Settings()
