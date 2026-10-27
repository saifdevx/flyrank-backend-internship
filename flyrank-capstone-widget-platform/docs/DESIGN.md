# Design document (Phase 1)

## Problem
Customers want a lead-capture form on a website they don't control. They define a widget, paste one `<script>` tag, and
visitors' submissions arrive in a dashboard. The visitor's browser talks to my API directly, so every request is
untrusted: it can be malformed, oversized, repeated, forged, or a flood.

## Three request paths (kept separate)
| Actor | Path | Trust |
|---|---|---|
| Owner | `/admin/*` (API key) | authenticated, tenant-scoped, **no CORS** |
| Customer's website | `GET /widget.js`, `GET /widgets/{id}/config` | public, cached, CORS `*` |
| Visitor | `POST /submissions` | public, CORS `*`, size-capped, rate-limited, spam-filtered |

## Data model (SQLite, schema in `migrations/001_init.sql`)
- `tenants(id, name, email, api_key_hash)` - a customer. Only a SHA-256 hash of the API key is stored.
- `widgets(id, tenant_id, type, title, description, fields_json, button_text, success_message, version)` - `tenant_id` is in
  every query, which is the whole isolation guarantee. `version` bumps on update.
- `submissions(id, widget_id, tenant_id, data_json, ip, geo_*, idempotency_key, created_at)` - unique `(widget_id, idempotency_key)`.
- `jobs(id, type, payload_json, status, attempts, last_error, run_at)` - the background queue.
- Indexes: `widgets(tenant_id)`, `submissions(tenant_id, created_at)`, `submissions(widget_id, created_at)`, the idempotency
  unique index, and `jobs(status, run_at)`.

## Layers
`routes/` (HTTP only) -> `services.py` (rules) -> `repositories.py` (SQL only). Side concerns: `geo.py`, `notify.py`,
`jobs.py`, `rate_limit.py`, `cors.py`. Routes never touch SQL; repositories never raise HTTP errors.

## The submission pipeline, in order (cheapest check first)
1. per-IP token bucket -> `429` 2. body size cap -> `413` 3. JSON parse -> `400` 4. widget exists -> `404`
5. per-widget token bucket -> `429` 6. honeypot -> silently dropped 7. validate against the widget's own fields -> `400`
8. idempotency key already seen -> `200 duplicate` 9. geo fallback chain (never raises) 10. store row **and** enqueue
notification job in one transaction 11. worker sends the email later, retries with backoff, alerts if it gives up.

## Key decisions
- **Foreign tenants get 404, not 403**, so IDs of other customers' widgets can't be probed.
- **Honeypot returns the same 201** as a real success, so a bot learns nothing.
- **Token bucket, not a fixed window**: a burst is allowed, floods get 429, and a normal request a second later works again.
- **Transactional outbox**: the row and its notification job commit together. The email itself can fail later without
  touching the submission.
- **Versioned bundle**: `widget.<hash>.js` is cached for a year because the hash changes when the file does.
- **No CORS on `/admin`**: only public paths are opened to other origins.

## Explicit non-goal
No per-widget allowed-origins list and no form-builder UI. Any website may embed any widget (that is how the public
embed model works); abuse is handled by rate limits, validation and the honeypot instead.
