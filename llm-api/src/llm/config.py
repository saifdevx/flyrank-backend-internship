"""Loads .env and gives small helpers to read settings. Everything is read at call time."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]   # the llm-api folder
load_dotenv(ROOT / ".env")


def env(name, default=None):
    value = os.getenv(name)
    return value if value not in (None, "") else default


def env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")
