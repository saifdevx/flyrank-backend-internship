"""Requirements: widget management, tenant isolation, embed snippet, cached delivery."""
import re

from app import bundle, db
from conftest import CONTACT_WIDGET, make_tenant, valid_submission


def test_admin_api_rejects_missing_or_wrong_key(client):
    assert client.get("/admin/widgets").status_code == 401
    assert client.get("/admin/widgets", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/admin/widgets", json=CONTACT_WIDGET).status_code == 401


def test_widget_crud_with_correct_status_codes(client, tenant_a):
    created = client.post("/admin/widgets", json=CONTACT_WIDGET, headers=tenant_a)
    assert created.status_code == 201
    wid = created.json()["id"]
    assert client.get("/admin/widgets", headers=tenant_a).json()[0]["id"] == wid
    assert client.get(f"/admin/widgets/{wid}", headers=tenant_a).status_code == 200
    updated = client.put(f"/admin/widgets/{wid}", json={**CONTACT_WIDGET, "title": "New title"}, headers=tenant_a)
    assert updated.status_code == 200 and updated.json()["title"] == "New title" and updated.json()["version"] == 2
    assert client.delete(f"/admin/widgets/{wid}", headers=tenant_a).status_code == 204
    assert client.get(f"/admin/widgets/{wid}", headers=tenant_a).status_code == 404


def test_widget_validation_returns_400_with_field_names(client, tenant_a):
    bad = {**CONTACT_WIDGET, "type": "banner", "fields": []}
    r = client.post("/admin/widgets", json=bad, headers=tenant_a)
    assert r.status_code == 400 and {f["field"] for f in r.json()["fields"]} >= {"type", "fields"}
    dup = {**CONTACT_WIDGET, "fields": [CONTACT_WIDGET["fields"][0], CONTACT_WIDGET["fields"][0]]}
    assert client.post("/admin/widgets", json=dup, headers=tenant_a).status_code == 400


def test_tenant_isolation(client, tenant_a, tenant_b, widget):
    wid = widget["id"]
    client.post("/submissions", json=valid_submission(wid))
    # tenant B cannot read, change, delete or embed tenant A's widget; and gets 404, not 403
    assert client.get(f"/admin/widgets/{wid}", headers=tenant_b).status_code == 404
    assert client.put(f"/admin/widgets/{wid}", json=CONTACT_WIDGET, headers=tenant_b).status_code == 404
    assert client.delete(f"/admin/widgets/{wid}", headers=tenant_b).status_code == 404
    assert client.get(f"/admin/widgets/{wid}/embed", headers=tenant_b).status_code == 404
    assert client.get("/admin/widgets", headers=tenant_b).json() == []
    # ...nor A's submissions
    assert client.get("/admin/submissions", headers=tenant_b).json()["total"] == 0
    assert client.get(f"/admin/submissions?widget_id={wid}", headers=tenant_b).json()["total"] == 0
    assert client.get("/admin/stats", headers=tenant_b).json()["total_submissions"] == 0
    # A still sees everything, and A's widget survived B's delete attempt
    assert client.get("/admin/submissions", headers=tenant_a).json()["total"] == 1


def test_api_key_is_stored_only_as_a_hash(client):
    r = client.post("/admin/tenants", json={"name": "X", "email": "x@example.com"})
    key = r.json()["api_key"]
    with db.session() as conn:
        stored = conn.execute("SELECT api_key_hash FROM tenants").fetchone()[0]
    assert key not in stored and len(stored) == 64


def test_embed_snippet_is_one_script_tag(client, tenant_a, widget):
    r = client.get(f"/admin/widgets/{widget['id']}/embed", headers=tenant_a)
    snippet = r.json()["snippet"]
    assert re.fullmatch(r'<script src="http://localhost:8000/widget\.[0-9a-f]{8}\.js\?id=' + widget["id"] + '"></script>', snippet)


def test_public_config_has_cache_headers_and_etag(client, widget):
    r = client.get(f"/widgets/{widget['id']}/config")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=60"
    assert "tenant" not in r.text and r.json()["honeypot_field"] == "website"
    again = client.get(f"/widgets/{widget['id']}/config", headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304
    assert client.get("/widgets/nope/config").status_code == 404


def test_widget_script_is_versioned_and_cached_for_a_year(client):
    r = client.get(f"/widget.{bundle.VERSION}.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    stale = client.get("/widget.deadbeef.js")                    # old snippet: works, but not cached long
    assert stale.status_code == 200 and stale.headers["cache-control"] == "public, max-age=300"
    assert client.get("/widget.js").headers["cache-control"] == "public, max-age=300"


def test_head_requests_work_on_public_assets(client, widget):
    """CDNs and uptime checkers send HEAD. Found by a live smoke test (it returned 405 before the fix)."""
    for url in ("/widget.js", f"/widget.{bundle.VERSION}.js", f"/widgets/{widget['id']}/config"):
        r = client.head(url)
        assert r.status_code == 200, url
        assert "max-age" in r.headers["cache-control"], url
