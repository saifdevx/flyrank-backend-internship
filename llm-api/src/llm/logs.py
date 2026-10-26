"""One JSON object per line. Used for the cost log and the quarantine log."""
import json
from datetime import datetime, timezone

from .config import ROOT

LOG_DIR = ROOT / "logs"


def write_jsonl(filename, record, echo=False):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **record}
    line = json.dumps(record, ensure_ascii=False)
    with open(LOG_DIR / filename, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if echo:
        print(line, flush=True)
