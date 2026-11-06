"""Settings from environment variables, loaded from backend/.env if present."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    kroger_client_id: str
    kroger_client_secret: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        kroger_client_id=os.environ.get("KROGER_CLIENT_ID", ""),
        kroger_client_secret=os.environ.get("KROGER_CLIENT_SECRET", ""),
    )
