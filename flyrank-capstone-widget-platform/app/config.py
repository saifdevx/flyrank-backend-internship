"""All settings, read from the environment (.env is git-ignored). Other modules read config.NAME at call time."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name, default):
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


DATABASE_PATH = os.getenv("DATABASE_PATH", str(ROOT / "data" / "app.db"))
LOG_DIR = Path(os.getenv("LOG_DIR", str(ROOT / "logs")))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "10240"))          # 10 KB is plenty for a form

# Token buckets: BURST requests at once, then REFILL per second
RATE_IP_BURST = float(os.getenv("RATE_IP_BURST", "10"))
RATE_IP_REFILL_PER_SEC = float(os.getenv("RATE_IP_REFILL_PER_SEC", "1"))
RATE_WIDGET_BURST = float(os.getenv("RATE_WIDGET_BURST", "60"))
RATE_WIDGET_REFILL_PER_SEC = float(os.getenv("RATE_WIDGET_REFILL_PER_SEC", "5"))
RATE_SIGNUP_BURST = float(os.getenv("RATE_SIGNUP_BURST", "5"))
RATE_SIGNUP_REFILL_PER_SEC = float(os.getenv("RATE_SIGNUP_REFILL_PER_SEC", "0.02"))

CONFIG_MAX_AGE = int(os.getenv("CONFIG_MAX_AGE", "60"))              # widget config: short cache
TRUST_PROXY = _bool("TRUST_PROXY", False)                            # read X-Forwarded-For only behind a proxy

GEO_MODE = os.getenv("GEO_MODE", "mock")                             # mock | real
GEO_TIMEOUT_SECONDS = float(os.getenv("GEO_TIMEOUT_SECONDS", "2"))

WORKER_ENABLED = _bool("WORKER_ENABLED", True)
JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
JOB_BACKOFF_SECONDS = float(os.getenv("JOB_BACKOFF_SECONDS", "2"))
JOB_POLL_SECONDS = float(os.getenv("JOB_POLL_SECONDS", "0.5"))

DEV_TOOLS = _bool("DEV_TOOLS", False)                                # /dev/* endpoints to force failures for the probes
