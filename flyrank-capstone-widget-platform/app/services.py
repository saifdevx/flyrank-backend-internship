"""Business logic: no SQL (that is repositories.py) and no HTTP details (that is routes/)."""
import json
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from . import bundle, config, db, geo, rate_limit, repositories as repo, security
from .errors import BadRequest, NotFound, RateLimited

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]+$")
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9_\-]{8,128}$")
HONEYPOT_FIELD = "website"


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


# ---- tenants ----
def create_tenant(name, email):
    api_key = security.new_api_key()
    with db.session() as conn:
        tenant_id = repo.create_tenant(conn, name, email, security.hash_key(api_key))
    return tenant_id, api_key          # the key is returned once; only its hash is stored


# ---- widgets ----
def _widget_dict(row):
    data = dict(row)
    data["fields"] = json.loads(data.pop("fields_json"))
    data["created_at"] = _iso(data["created_at"])
    data["updated_at"] = _iso(data["updated_at"])
    return data


def create_widget(tenant_id, payload, widget_id=None):
    widget_id = widget_id or secrets.token_hex(5)
    with db.session() as conn:
        repo.insert_widget(conn, widget_id, tenant_id, payload.model_dump())
        return _widget_dict(repo.get_widget_for_tenant(conn, widget_id, tenant_id))


def list_widgets(tenant_id):
    with db.session() as conn:
        return [_widget_dict(r) for r in repo.list_widgets(conn, tenant_id)]


def get_widget(tenant_id, widget_id):
    with db.session() as conn:
        row = repo.get_widget_for_tenant(conn, widget_id, tenant_id)
    if row is None:
        raise NotFound("Widget not found")      # 404, not 403: do not reveal that another tenant owns it
    return _widget_dict(row)


def update_widget(tenant_id, widget_id, payload):
    with db.session() as conn:
        if not repo.update_widget(conn, widget_id, tenant_id, payload.model_dump()):
            raise NotFound("Widget not found")
        return _widget_dict(repo.get_widget_for_tenant(conn, widget_id, tenant_id))


def delete_widget(tenant_id, widget_id):
    with db.session() as conn:
        if not repo.delete_widget(conn, widget_id, tenant_id):
            raise NotFound("Widget not found")


def embed_snippet(tenant_id, widget_id):
    get_widget(tenant_id, widget_id)             # also enforces ownership
    src = f"{config.PUBLIC_BASE_URL}/widget.{bundle.VERSION}.js?id={widget_id}"
    return {"widget_id": widget_id, "src": src, "snippet": f'<script src="{src}"></script>'}


def public_config(widget_id):
    with db.session() as conn:
        row = repo.get_widget_public(conn, widget_id)
    if row is None:
        raise NotFound("Widget not found")
    w = _widget_dict(row)
    return {                                     # only what a visitor's browser needs: no tenant info
        "id": w["id"], "type": w["type"], "title": w["title"], "description": w["description"],
        "fields": w["fields"], "button_text": w["button_text"], "success_message": w["success_message"],
        "version": w["version"], "submit_url": f"{config.PUBLIC_BASE_URL}/submissions",
        "honeypot_field": HONEYPOT_FIELD,
    }


# ---- submissions ----
def validate_data(field_defs, data):
    """Check a visitor's answers against the widget's own field list. Returns (clean, errors)."""
    if not isinstance(data, dict):
        return {}, [{"field": "data", "message": "must be an object"}]
    errors, clean = [], {}
    known = {f["name"] for f in field_defs}
    for name in data:
        if name not in known:
            errors.append({"field": str(name)[:50], "message": "unknown field"})
    for f in field_defs:
        value = data.get(f["name"])
        if value is None or (isinstance(value, str) and not value.strip()):
            if f["required"]:
                errors.append({"field": f["name"], "message": "is required"})
            continue
        if not isinstance(value, str):
            errors.append({"field": f["name"], "message": "must be text"})
            continue
        value = value.strip()
        if "\x00" in value:
            errors.append({"field": f["name"], "message": "contains invalid characters"})
        elif len(value) > f["max_length"]:
            errors.append({"field": f["name"], "message": f"must be at most {f['max_length']} characters"})
        elif f["type"] == "email" and not EMAIL_RE.match(value):
            errors.append({"field": f["name"], "message": "must be a valid email address"})
        else:
            clean[f["name"]] = value
    return clean, errors


def check_idempotency_key(key):
    if key is not None and not IDEMPOTENCY_RE.match(key):
        raise BadRequest("Invalid Idempotency-Key", fields=[{"field": "Idempotency-Key",
                         "message": "must be 8-128 characters: letters, digits, - and _"}])


def submit(payload, ip, idempotency_key):
    """The hardened path. Returns ("created" | "duplicate" | "spam"). Raises AppError for 4xx."""
    if not isinstance(payload, dict):
        raise BadRequest("Body must be a JSON object")
    widget_id = payload.get("widget_id")
    if not isinstance(widget_id, str) or not 1 <= len(widget_id) <= 64:
        raise BadRequest("Invalid submission", fields=[{"field": "widget_id", "message": "must be a string of 1-64 characters"}])

    with db.session() as conn:
        row = repo.get_widget_public(conn, widget_id)
    if row is None:
        raise NotFound("Widget not found")

    # per-widget limit comes after the lookup, so random ids cannot fill memory with junk buckets
    allowed, retry = rate_limit.limiter.consume(f"widget:{widget_id}", config.RATE_WIDGET_BURST, config.RATE_WIDGET_REFILL_PER_SEC)
    if not allowed:
        raise RateLimited(retry)

    # Honeypot: a human never sees this field. Drop silently, answer like a success so bots learn nothing.
    if payload.get(HONEYPOT_FIELD) not in (None, ""):
        return "spam"

    widget = _widget_dict(row)
    clean, errors = validate_data(widget["fields"], payload.get("data"))
    if errors:
        raise BadRequest("Invalid submission", fields=errors)

    if idempotency_key:
        with db.session() as conn:
            if repo.find_submission_by_key(conn, widget_id, idempotency_key):
                return "duplicate"

    enriched = geo.enrich(ip)                    # never raises; None if every provider failed

    try:
        with db.session() as conn:
            submission_id = repo.insert_submission(conn, widget_id, widget["tenant_id"], json.dumps(clean),
                                                   ip, enriched, idempotency_key)
            # Same transaction: the row and its notification job are saved together or not at all.
            # The slow, failure-prone part (sending email) happens later in the worker.
            repo.enqueue_job(conn, "notify_new_submission", {"submission_id": submission_id})
    except sqlite3.IntegrityError:               # two retries raced: the unique index let only one in
        return "duplicate"
    return "created"


# ---- dashboard ----
def list_submissions(tenant_id, widget_id, limit, offset):
    with db.session() as conn:
        rows, total = repo.list_submissions(conn, tenant_id, widget_id, limit, offset)
    items = []
    for r in rows:
        geo_info = None
        if r["geo_provider"]:
            geo_info = {"country": r["geo_country"], "city": r["geo_city"], "provider": r["geo_provider"]}
        items.append({"id": r["id"], "widget_id": r["widget_id"], "data": json.loads(r["data_json"]),
                      "ip": r["ip"], "geo": geo_info, "created_at": _iso(r["created_at"])})
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def stats(tenant_id):
    since = time.time() - 30 * 86400
    with db.session() as conn:
        total, per_widget, by_day, geo_rows = repo.stats(conn, tenant_id, since)
    return {
        "total_submissions": total,
        "per_widget": [dict(r) for r in per_widget],
        "last_30_days": [dict(r) for r in by_day],
        "geo_breakdown": [dict(r) for r in geo_rows],
    }
