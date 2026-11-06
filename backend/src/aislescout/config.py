"""Settings from environment variables, loaded from backend/.env if present."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_KEYS_DIR = BACKEND_DIR / "keys"  # gitignored


@dataclass(frozen=True)
class Settings:
    kroger_client_id: str
    kroger_client_secret: str
    walmart_consumer_id: str
    walmart_private_key_path: Path
    walmart_key_version: str
    walmart_publisher_id: str

    @property
    def kroger_configured(self) -> bool:
        return bool(self.kroger_client_id and self.kroger_client_secret)

    @property
    def walmart_configured(self) -> bool:
        return bool(self.walmart_consumer_id) and self.walmart_private_key_path.is_file()


def load_settings() -> Settings:
    load_dotenv(BACKEND_DIR / ".env")
    key_path = Path(os.environ.get("WALMART_PRIVATE_KEY_PATH") or DEFAULT_KEYS_DIR / "walmart_private_key.pem")
    if not key_path.is_absolute():
        key_path = BACKEND_DIR / key_path
    return Settings(
        kroger_client_id=os.environ.get("KROGER_CLIENT_ID", ""),
        kroger_client_secret=os.environ.get("KROGER_CLIENT_SECRET", ""),
        walmart_consumer_id=os.environ.get("WALMART_CONSUMER_ID", ""),
        walmart_private_key_path=key_path,
        walmart_key_version=os.environ.get("WALMART_KEY_VERSION", "1"),
        walmart_publisher_id=os.environ.get("WALMART_PUBLISHER_ID", ""),
    )
