"""Reads the bot's settings from the .env file / environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    discord_token: str
    anthropic_api_key: str
    anthropic_model: str = "claude-haiku-5-5"
    whisper_model: str = "base"
    instagram_cookies_file: str | None = None
    data_dir: Path = Path("data")  # where the bot saves its chosen channels
    max_media_items: int = 10  # Discord allows 10 files per message, the size of a full carousel
    max_places: int = 5  # cap for posts that list many places, to avoid spamming the channel

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        required = ("DISCORD_TOKEN", "ANTHROPIC_API_KEY")
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            raise ConfigError(f"Missing in .env: {', '.join(missing)}")

        return cls(
            discord_token=os.environ["DISCORD_TOKEN"].strip(),
            anthropic_api_key=os.environ["ANTHROPIC_API_KEY"].strip(),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "").strip() or cls.anthropic_model,
            whisper_model=os.getenv("WHISPER_MODEL", "").strip() or cls.whisper_model,
            instagram_cookies_file=os.getenv("INSTAGRAM_COOKIES_FILE", "").strip() or None,
            data_dir=Path(os.getenv("DATA_DIR", "").strip() or cls.data_dir),
        )
