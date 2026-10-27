# Embeddable Widget & Lead-Capture Platform

FlyRank Backend capstone. Customers define a widget (a contact or signup form), paste **one `<script>` tag** on any website,
and visitors' submissions arrive in an authenticated dashboard API. Because browsers on sites I don't control call the API
directly, the submission path is built to survive bad input, floods, spam and broken dependencies.

Stack: Python, FastAPI, SQLite (with migrations), a background worker thread. No Docker, no paid services.

## Architecture

```
 Widget owner (API key)                  Customer website (any origin)               Visitor
        |                                         |                                     |
        | /admin/*  (no CORS)                     | <script src=".../widget.<hash>.js?id=abc">
        v                                         v                                     |
 +--------------+                      GET /widgets/{id}/config  (public, CORS, cached)  |
 | Admin routes |                      GET /widget.<hash>.js     (public, CORS, 1y cache)|
 +------+-------+                                                                       |
        |                                          POST /submissions  (public, CORS) <--+
        |                                                   |
        |                       per-IP rate limit -> 429    |
        |                       size cap -> 413             |
        |                       bad JSON/fields -> 400      |
        |                       per-widget rate limit -> 429|
        |                       honeypot -> dropped         |
        |                       geo: provider A -> B -> none (never fails the request)
        v                                                   v
 +-----------------------------------------------------------------+
 | services.py (rules)  ->  repositories.py (SQL)  ->  SQLite      |
 |   widgets | submissions | tenants | jobs   (tenant_id in every query)
 +----------------------------+------------------------------------+
                              | same transaction as the submission
                              v
                  jobs table -> worker thread -> email (retry x3, backoff, ALERT on give-up)
```

More detail and the reasoning behind each decision: [docs/DESIGN.md](docs/DESIGN.md).

## Run it (about 3 minutes, Python 3.10+)

```bash
python -m venv venv
venv\Scripts\Activate.ps1          # Windows PowerShell   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env             # macOS/Linux: cp .env.example .env
python -m app.seed                 # creates two demo tenants + widgets, prints their API keys
uvicorn app.main:app --port 8000
```

Docs: http://localhost:8000/docs . Run the tests with `python -m pytest -q`.

### See the widget on a "customer site" (a different origin)

```bash
python -m http.server 5500 --directory customer-site
```

Open http://localhost:5500. The form is loaded from port 8000, so the browser enforces real CORS. Submit it, then:

```bash
curl http://localhost:8000/admin/submissions -H "Authorization: Bearer <tenant A key from the seed output>"
```

## API

| Method | Path | Auth | What it does |
|---|---|---|---|
| POST | `/admin/tenants` | none (rate-limited) | Create an account; returns an API key **once** |
| POST/GET | `/admin/widgets` | Bearer key | Create / list my widgets |
| GET/PUT/DELETE | `/admin/widgets/{id}` | Bearer key | Read / replace / delete one of my widgets |
| GET | `/admin/widgets/{id}/embed` | Bearer key | The one-line `<script>` snippet |
| GET | `/admin/submissions?widget_id=&limit=&offset=` | Bearer key | My submissions, paginated |
| GET | `/admin/stats` | Bearer key | Totals, per widget, last 30 days, by country |
| GET | `/widget.js?id=` , `/widget.<hash>.js?id=` | public | The widget script (versioned URL cached 1 year, immutable) |
| GET | `/widgets/{id}/config` | public | Widget settings, `Cache-Control: max-age=60`, ETag |
| POST | `/submissions` | public | Submit a form (CORS, size cap, rate limit, honeypot, validation) |
| GET | `/health` | public | Liveness |

Status codes: `201` created, `200` duplicate (idempotent retry), `400` invalid input (JSON body names the fields), `401` bad/missing
API key, `404` unknown widget (also for other tenants' widgets), `413` payload too large, `429` rate limited (with `Retry-After`).
Every error is JSON: `{"error": "..."}`.

## Prove the failure handling yourself (dev switches)

With `DEV_TOOLS=1` (set in `.env.example`) these endpoints force failures:

```bash
curl -X POST localhost:8000/dev/toggles -H "Content-Type: application/json" -d "{\"geo_a_down\": true}"            # provider B answers
curl -X POST localhost:8000/dev/toggles -H "Content-Type: application/json" -d "{\"geo_a_down\": true, \"geo_b_down\": true}"   # stored, no geo
curl -X POST localhost:8000/dev/toggles -H "Content-Type: application/json" -d "{\"email_fail\": true}"             # submit still returns 201
```

The deterministic versions of all six acceptance probes are in `tests/`. `python scripts/fill_evidence.py` runs them and writes
[EVIDENCE.md](EVIDENCE.md).

## Limitations (honest)

- **Rate limits live in memory.** They reset on restart and are per process. Several servers would need a shared store such as Redis.
- **SQLite is a single-node database.** Fine for this scope. A multi-server deployment would move to Postgres (the SQL is plain).
- **The job queue is a polling thread** in the API process, with at-least-once delivery: a crash mid-job re-runs it. A real
  deployment would run the worker separately.
- **Email is a console log.** Only `notify.py` would change to use SMTP or Mailpit.
- **Geo:** `GEO_MODE=mock` is the default so the fallback is provable. `GEO_MODE=real` uses ip-api.com then ipapi.co, which
  skip localhost and private addresses and have free-tier quotas.
- **`DEV_TOOLS=1` exposes endpoints that break things on purpose.** It must be off in production.
- **Any website can embed any widget** (no origin allow-list), and deleting a widget deletes its submissions.
- **`TRUST_PROXY` is off.** Behind a reverse proxy, turn it on so rate limits see the visitor's IP, not the proxy's.
