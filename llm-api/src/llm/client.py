"""The model call: explicit timeout, retry policy, cost log.

Design choices (also written in the README):
- The SDK's own retries are switched OFF (max_retries=0). My retry loop below is the only one,
  so one request can never silently turn into six calls.
- Retried: timeouts, connection errors, 429, 5xx.  Never retried: 400, 401, 403 and other 4xx.
"""
import random
import time

import openai
from openai import OpenAI

from . import config
from .logs import write_jsonl


class LLMError(Exception):
    """Base class. Each subclass knows which HTTP status the caller should see."""
    status_code = 500

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class LLMConfigError(LLMError):
    status_code = 500


class LLMTimeout(LLMError):
    status_code = 504


class LLMProviderRejected(LLMError):
    status_code = 502


class LLMUnavailable(LLMError):
    status_code = 502


def get_client():
    missing = [n for n in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if not config.env(n)]
    if missing:
        raise LLMConfigError(f"LLM is not configured: set {', '.join(missing)} in .env")
    timeout = min(float(config.env("LLM_TIMEOUT_SECONDS", "30")), 60.0)   # never the 10-minute default
    return OpenAI(
        base_url=config.env("LLM_BASE_URL"),
        api_key=config.env("LLM_API_KEY"),
        timeout=timeout,
        max_retries=0,
    )


def _retry_after_seconds(error):
    """If a 429 says how long to wait, obey it (capped) instead of guessing."""
    try:
        value = error.response.headers.get("retry-after")
        return min(float(value), 30.0) if value is not None else None
    except Exception:
        return None


def call_model(messages, prompt_version, repair=False):
    """Call the model and return its raw text. Logs one line per attempt."""
    client = get_client()
    model = config.env("LLM_MODEL")
    max_attempts = int(config.env("LLM_MAX_RETRIES", "2")) + 1
    backoff_base = float(config.env("LLM_BACKOFF_BASE_SECONDS", "1"))
    last_kind = "unknown"

    for attempt in range(1, max_attempts + 1):
        started = time.monotonic()
        wait = None
        try:
            res = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=int(config.env("LLM_MAX_TOKENS", "600")),
            )
        except openai.APITimeoutError:
            last_kind = "timeout"
        except openai.APIConnectionError:
            last_kind = "connection_error"
        except openai.RateLimitError as e:
            last_kind = "http_429"
            wait = _retry_after_seconds(e)
        except openai.InternalServerError as e:
            last_kind = f"http_{e.status_code}"
        except openai.APIStatusError as e:
            # 400 / 401 / 403 / 404 ...: asking again changes nothing, so fail fast, no retry
            _log_call(prompt_version, model, None, started, repair, attempt, ok=False, error=f"http_{e.status_code}")
            raise LLMProviderRejected(
                f"The model provider rejected the request (HTTP {e.status_code}). "
                "Check LLM_API_KEY, LLM_MODEL and your provider settings."
            )
        else:
            _log_call(prompt_version, model, res.usage, started, repair, attempt, ok=True)
            return res.choices[0].message.content or ""

        _log_call(prompt_version, model, None, started, repair, attempt, ok=False, error=last_kind)
        if attempt < max_attempts:
            time.sleep(wait if wait is not None else backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.5))

    if last_kind == "timeout":
        raise LLMTimeout("The model took too long to answer. Please try again.")
    raise LLMUnavailable("The model provider is unavailable right now. Please try again later.")


def _log_call(prompt_version, model, usage, started, repair, attempt, ok, error=None):
    record = {
        "event": "llm_call",
        "prompt_version": prompt_version,
        "model": model,
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "repair": repair,
        "attempt": attempt,
        "ok": ok,
    }
    if error:
        record["error"] = error
    write_jsonl("llm-calls.jsonl", record, echo=True)
