"""validate input -> kill switch / stub -> build prompt -> call model -> parse -> validate -> repair once -> 422."""
import json
import re

from pydantic import ValidationError

from . import config
from .client import LLMConfigError, LLMError, call_model
from .logs import write_jsonl
from .schema import TriageResult

STUB = TriageResult(category="other", urgency="normal", confidence=0.5,
                    reason="Stub mode: no model was called.")
FALLBACK = TriageResult(category="other", urgency="normal", confidence=0.0,
                        reason="AI triage is switched off, so this was routed to manual review.")


class OutputInvalid(LLMError):
    status_code = 422


def load_prompt(version):
    path = config.ROOT / "prompts" / f"triage-{version}.md"
    if not path.exists():
        raise LLMConfigError(f"Prompt file not found: prompts/triage-{version}.md")
    return path.read_text(encoding="utf-8")


def extract_json(text):
    """Models love code fences and 'Sure! Here is the JSON:'. Strip that and find the object."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in the output")
    return json.loads(text[start:end + 1])


def parse_output(raw):
    """Return (result, None) on success or (None, error_message) on failure."""
    try:
        return TriageResult.model_validate(extract_json(raw)), None
    except ValidationError as e:
        # only field name + rule, never the model's own text
        problems = "; ".join(f"{'.'.join(str(p) for p in err['loc']) or 'output'}: {err['msg']}" for err in e.errors())
        return None, f"The JSON did not match the schema ({problems})."
    except json.JSONDecodeError as e:
        return None, f"The output was not valid JSON ({e.msg} at position {e.pos})."
    except ValueError as e:
        return None, f"The output was not usable ({e})."


def run_triage(text):
    # Kill switch first: no model call, no cost, deterministic answer.
    if not config.env_bool("LLM_ENABLED", True):
        return FALLBACK
    # Stub mode: build and debug without spending a single call.
    if config.env("LLM_STUB") == "1":
        return STUB

    version = config.env("PROMPT_VERSION", "v1")
    system_prompt = load_prompt(version)
    messages = [
        {"role": "system", "content": system_prompt},
        # untrusted text lives only in the user message, JSON-encoded so it cannot break out of its quotes
        {"role": "user", "content": json.dumps({"text": text}, ensure_ascii=False)},
    ]

    raw = call_model(messages, version, repair=False)
    result, error = parse_output(raw)
    if result:
        return result

    # Repair once, and only once: hand the model its own mistake.
    repair_messages = messages + [
        {"role": "assistant", "content": raw or "(empty answer)"},
        {"role": "user", "content": f"Your previous answer was rejected for this reason: {error} "
                                    "Return only corrected JSON matching the schema."},
    ]
    raw2 = call_model(repair_messages, version, repair=True)
    result, error2 = parse_output(raw2)
    if result:
        return result

    write_jsonl("quarantine.jsonl", {
        "prompt_version": version,
        "model": config.env("LLM_MODEL"),
        "input": text,
        "first_output": raw,
        "first_error": error,
        "second_output": raw2,
        "second_error": error2,
    })
    # never return the raw model text to the caller
    raise OutputInvalid("The model's answer did not match the required format, even after one repair attempt. "
                        "It has been quarantined for review.")
