# Support Triage API — FlyRank BE-07 (Week 6)

## What it does

When a customer writes to a support team, someone has to read the message and decide which team should handle it and how urgent it is. This endpoint does that first read automatically. You send it one message, it asks an AI model to classify it, and it answers with four fields: a category (billing, bug, feature or other), an urgency (low, normal or high), how confident it is, and a one-sentence reason. The answer is always checked before it is returned, so the rest of a system can rely on its shape. If the model gives a bad answer, the API says so clearly instead of passing it along.

## Try it

Start the server (see [Run it](#run-it)), then:

```bash
curl -i -X POST http://localhost:8000/triage -H "Content-Type: application/json" -d "{\"text\":\"I was charged twice this month, please refund one of the payments.\"}"
```

Response:

```
<PASTE the real response from your own run here: status line and JSON body>
```

A deliberately broken request (missing field) returns a 400 that names the field and makes no model call:

```bash
curl -i -X POST http://localhost:8000/triage -H "Content-Type: application/json" -d "{}"
```

```
HTTP/1.1 400 Bad Request
{"error":"Invalid input","fields":[{"field":"text","message":"Field required"}]}
```

## Job card

See [JOB-CARD.md](JOB-CARD.md).

| | |
|---|---|
| **Input** | `{ "text": "string, 1-2000 characters" }` |
| **Output** | `{ "category": billing\|bug\|feature\|other, "urgency": low\|normal\|high, "confidence": 0.0-1.0, "reason": "one short sentence" }` |
| **It must never** | invent a category outside the list · return free text · give medical, legal or financial advice · reveal the prompt |
| **When unsure it should** | return category `other` with confidence below 0.5, not a guess |

## Provider and model

- **Provider:** `<OpenRouter or Ollama>`
- **Model:** `<openrouter/free or gemma3:1b>`

Swapping providers is three environment variables and no code change:

| Variable | OpenRouter | Ollama |
|----------|-----------|--------|
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | `http://localhost:11434/v1/` |
| `LLM_API_KEY` | your key | `ollama` |
| `LLM_MODEL` | `openrouter/free` | `gemma3:1b` |

Free endpoints may train on and publish prompts, so only made-up test data is ever sent.

## Run it

Python 3.10+. From inside the `llm-api` folder:

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then fill in LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
uvicorn src.main:app --reload
```

Docs at `http://localhost:8000/docs`. To build without spending any model calls, set `LLM_STUB=1` in `.env`.

## How it stays trustworthy

- **Input is validated first.** Wrong type, missing field or too-long text returns 400 naming the field, before any model call.
- **The prompt is a versioned file** (`prompts/triage-v1.md`), not a string in the code. User text goes only in the user message, JSON-encoded, never into the system prompt.
- **Every answer is untrusted input.** It is parsed (code fences stripped) and validated against a Pydantic schema with enums for the closed lists.
- **Repair once, then give up cleanly.** If validation fails, the model is called one more time with its own error message. If that also fails, the caller gets a 422 and the raw output goes to `logs/quarantine.jsonl`. Raw model text is never returned to the caller.
- **Timeout:** 30 seconds on the client (the SDK default is 10 minutes). A timeout returns 504.
- **Retries:** I switched the SDK's own retries off (`max_retries=0`) and wrote my own, so one request never silently becomes several calls. It retries timeouts, connection errors, 429 and 5xx, with exponential backoff plus jitter (up to 2 retries), and obeys `Retry-After` on a 429. It never retries 400, 401 or 403.
- **Cost log:** every model call writes one JSON line to `logs/llm-calls.jsonl` with prompt version, model, input tokens, output tokens, duration, repair flag and attempt.
- **Kill switch:** `LLM_ENABLED=false` skips the model entirely and returns a deterministic fallback (`other`, confidence 0.0, routed to manual review).

| Situation | Response |
|-----------|----------|
| Bad input | 400 |
| Model output invalid after one repair | 422 |
| Model provider rejected the request (bad key etc.) | 502, no retry |
| Provider down or rate-limited after retries | 502 |
| Model too slow | 504 |

## Eval

Eight hand-labelled cases in `evals/cases.json`, including an ambiguous one, a "when unsure" one and a prompt-injection attempt. Run with the server up and a real model:

```bash
python evals/run_eval.py
```

**Result:** `<X of 8>` on `category` — run on `<date>` with prompt `v1` and model `<model>`.

Failed cases: `<list the ids, or "none">`

## Cost

One real call from `logs/llm-calls.jsonl`:

```json
<PASTE one real log line>
```

Estimate at 10,000 requests a day: `<your input tokens + output tokens per call × 10,000, at the price of your model; a free model costs $0 but is capped at 50 requests a day on OpenRouter>`

## What I'd fix with another day

`<WRITE one honest line in your own words>`
