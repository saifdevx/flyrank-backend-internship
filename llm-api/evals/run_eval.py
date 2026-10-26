"""Run the 8 labelled cases through the running endpoint and report how many matched.

1. Start the server (with a REAL model: LLM_STUB unset, LLM_ENABLED not false).
2. In another terminal, from the llm-api folder:  python evals/run_eval.py
"""
import json
import os
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

URL = os.getenv("EVAL_URL", "http://localhost:8000/triage")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")
DELAY_SECONDS = 4   # stay under the free tier's 20 requests per minute

cases = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
results, failed = [], []
category_hits = urgency_hits = 0

for case in cases:
    try:
        resp = requests.post(URL, json={"text": case["text"]}, timeout=120)
        body = resp.json()
    except Exception as e:
        resp, body = None, {"error": str(e)}

    if resp is not None and resp.status_code == 200:
        got_category, got_urgency = body.get("category"), body.get("urgency")
        category_ok = got_category == case["expected_category"]
        urgency_ok = got_urgency == case["expected_urgency"]
    else:
        got_category = got_urgency = None
        category_ok = urgency_ok = False

    category_hits += category_ok
    urgency_hits += urgency_ok
    status = resp.status_code if resp is not None else "no response"
    print(f"[{'PASS' if category_ok else 'FAIL'}] case {case['id']} ({case['kind']}): "
          f"expected {case['expected_category']}, got {got_category} (HTTP {status})")
    if not category_ok:
        failed.append(case["id"])
    results.append({**case, "got_category": got_category, "got_urgency": got_urgency,
                    "http_status": status, "category_ok": category_ok})
    time.sleep(DELAY_SECONDS)

total = len(cases)
summary = {
    "date": date.today().isoformat(),
    "prompt_version": PROMPT_VERSION,
    "category_score": f"{category_hits} of {total}",
    "category_percent": round(100 * category_hits / total),
    "urgency_score_info_only": f"{urgency_hits} of {total}",
    "failed_case_ids": failed,
}
print("\n" + json.dumps(summary, indent=2))
(ROOT / "evals" / "last-run.json").write_text(
    json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
