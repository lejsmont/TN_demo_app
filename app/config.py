"""Application configuration and env validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List

from dotenv import load_dotenv


def load_env() -> None:
    """Load environment variables from .env if present."""
    load_dotenv(override=False)


@dataclass
class AppConfig:
    app_name: str = "Consents & Transaction Notifications Demo"
    env: str = "development"
    debug: bool = True

    @classmethod
    def from_env(cls) -> "AppConfig":
        env = os.getenv("FLASK_ENV", "development")
        debug = os.getenv("FLASK_DEBUG", "1") == "1"
        app_name = os.getenv("APP_NAME", cls.app_name)
        return cls(app_name=app_name, env=env, debug=debug)

    @staticmethod
    def validate_required(required: Iterable[str]) -> None:
        missing: List[str] = [key for key in required if not os.getenv(key)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    def as_flask_dict(self) -> dict:
        return {
            "ENV": self.env,
            "DEBUG": self.debug,
            "APP_NAME": self.app_name,
        }
