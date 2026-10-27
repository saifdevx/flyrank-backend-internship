"""The six acceptance probes from the capstone brief, run deterministically."""
import json
import time

from app import config, db, jobs
from conftest import valid_submission

CROSS_ORIGIN = {"Origin": "http://localhost:5500"}


def test_cors_preflight_and_headers(client, widget):
    pre = client.options("/submissions", headers={**CROSS_ORIGIN, "Access-Control-Request-Method": "POST",
                                                  "Access-Control-Request-Headers": "content-type,idempotency-key"})
    assert pre.status_code == 204
    assert pre.headers["access-control-allow-origin"] == "*"
    assert "POST" in pre.headers["access-control-allow-methods"]
    assert "Idempotency-Key" in pre.headers["access-control-allow-headers"]
    r = client.post("/submissions", json=valid_submission(widget["id"]), headers=CROSS_ORIGIN)
    assert r.headers["access-control-allow-origin"] == "*"
    assert client.get(f"/widgets/{widget['id']}/config", headers=CROSS_ORIGIN).headers["access-control-allow-origin"] == "*"
    # the admin API is NOT opened to every website
    assert "access-control-allow-origin" not in client.get("/admin/widgets", headers=CROSS_ORIGIN).headers


def test_probe1_valid_cross_origin_submission_is_stored_and_in_dashboard(client, tenant_a, widget):
    r = client.post("/submissions", json=valid_submission(widget["id"]), headers=CROSS_ORIGIN)
    assert r.status_code == 201 and r.json() == {"status": "received"}
    items = client.get("/admin/submissions", headers=tenant_a).json()["items"]
    assert len(items) == 1 and items[0]["data"]["email"] == "ada@example.com" and items[0]["widget_id"] == widget["id"]
    stats = client.get("/admin/stats", headers=tenant_a).json()
    assert stats["total_submissions"] == 1 and stats["per_widget"][0]["submissions"] == 1
    assert stats["geo_breakdown"][0]["country"] == "Mockland" and len(stats["last_30_days"]) == 1


def test_probe2_malformed_and_oversized_payloads_get_clean_4xx_never_500(client, widget):
    wid = widget["id"]
    cases = {
        "not json": client.post("/submissions", content="{nope", headers={"Content-Type": "application/json"}),
        "json but not an object": client.post("/submissions", json=["a"]),
        "missing widget_id": client.post("/submissions", json={"data": {}}),
        "data not an object": client.post("/submissions", json={"widget_id": wid, "data": "x"}),
        "missing required field": client.post("/submissions", json={"widget_id": wid, "data": {"name": "Ada"}}),
        "unknown field": client.post("/submissions", json={"widget_id": wid, "data": {"name": "A", "email": "a@b.co", "evil": "x"}}),
        "bad email": client.post("/submissions", json={"widget_id": wid, "data": {"name": "A", "email": "not-an-email"}}),
        "field too long": client.post("/submissions", json={"widget_id": wid, "data": {"name": "A", "email": "a@b.co", "message": "x" * 101}}),
        "wrong type": client.post("/submissions", json={"widget_id": wid, "data": {"name": 123, "email": "a@b.co"}}),
        "bad idempotency key": client.post("/submissions", json=valid_submission(wid), headers={"Idempotency-Key": "short"}),
    }
    for name, r in cases.items():
        assert r.status_code == 400, (name, r.status_code, r.text)
        assert "error" in r.json(), name
    assert client.post("/submissions", json=valid_submission("no-such-widget")).status_code == 404
    big = client.post("/submissions", json={"widget_id": wid, "data": {"name": "x" * 20000, "email": "a@b.co"}})
    assert big.status_code == 413 and "error" in big.json()
    assert cases["unknown field"].json()["fields"][0]["field"] == "evil"


def test_probe3_burst_gets_429_and_service_recovers(client, widget):
    config.RATE_IP_BURST, config.RATE_IP_REFILL_PER_SEC = 5, 1
    codes = [client.post("/submissions", json=valid_submission(widget["id"])).status_code for _ in range(12)]
    assert codes[:5] == [201] * 5 and 429 in codes
    limited = client.post("/submissions", json=valid_submission(widget["id"]))
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
    assert client.get("/health").status_code == 200                       # the service itself is fine
    time.sleep(1.2)                                                       # one token refills
    assert client.post("/submissions", json=valid_submission(widget["id"])).status_code == 201


def test_per_widget_limit(client, widget):
    config.RATE_WIDGET_BURST, config.RATE_WIDGET_REFILL_PER_SEC = 3, 0.01
    codes = [client.post("/submissions", json=valid_submission(widget["id"])).status_code for _ in range(5)]
    assert codes == [201, 201, 201, 429, 429]


def test_probe4_geo_fallback_chain(client, tenant_a, widget):
    def last_geo():
        return client.get("/admin/submissions", headers=tenant_a).json()["items"][0]["geo"]

    assert client.post("/submissions", json=valid_submission(widget["id"])).status_code == 201
    assert last_geo()["provider"] == "A"
    client.post("/dev/toggles", json={"geo_a_down": True})
    assert client.post("/submissions", json=valid_submission(widget["id"])).status_code == 201
    assert last_geo()["provider"] == "B"                                   # A down -> B answered
    client.post("/dev/toggles", json={"geo_b_down": True})
    r = client.post("/submissions", json=valid_submission(widget["id"]))
    assert r.status_code == 201 and last_geo() is None                     # both down -> stored anyway, no geo
    assert client.get("/admin/submissions", headers=tenant_a).json()["total"] == 3


def test_probe5_failing_side_effect_never_blocks_the_submission(client, tenant_a, widget, capsys):
    client.post("/dev/toggles", json={"email_fail": True})
    r = client.post("/submissions", json=valid_submission(widget["id"]))
    assert r.status_code == 201
    assert client.get("/admin/submissions", headers=tenant_a).json()["total"] == 1     # stored
    for _ in range(config.JOB_MAX_ATTEMPTS):                                           # worker retries, then gives up
        assert jobs.process_one() is True
    assert jobs.process_one() is False
    with db.session() as conn:
        job = conn.execute("SELECT status, attempts, last_error FROM jobs").fetchone()
    assert job["status"] == "failed" and job["attempts"] == config.JOB_MAX_ATTEMPTS and "unavailable" in job["last_error"]
    assert "ALERT job 1" in (config.LOG_DIR / "alerts.log").read_text()                # failure alert raised


def test_background_job_sends_notification_when_email_works(client, widget, capsys):
    client.post("/submissions", json=valid_submission(widget["id"]))
    assert jobs.process_one() is True
    assert "EMAIL -> a@example.com: new lead #1" in capsys.readouterr().out
    with db.session() as conn:
        assert conn.execute("SELECT status FROM jobs").fetchone()[0] == "done"


def test_job_that_fails_once_is_retried_and_succeeds(client, widget):
    client.post("/dev/toggles", json={"email_fail": True})
    client.post("/submissions", json=valid_submission(widget["id"]))
    assert jobs.process_one() is True                                      # attempt 1 fails
    client.post("/dev/toggles", json={"email_fail": False})                # provider recovers
    assert jobs.process_one() is True                                      # attempt 2 succeeds
    with db.session() as conn:
        row = conn.execute("SELECT status, attempts FROM jobs").fetchone()
    assert row["status"] == "done" and row["attempts"] == 1


def test_probe6_honeypot_blocks_bots_silently(client, tenant_a, widget):
    r = client.post("/submissions", json=valid_submission(widget["id"], website="http://buy-pills.example"))
    assert r.status_code == 201 and r.json() == {"status": "received"}     # looks like success to the bot
    assert client.get("/admin/submissions", headers=tenant_a).json()["total"] == 0   # but nothing was stored
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0           # and no email was queued
    ok = client.post("/submissions", json=valid_submission(widget["id"], website=""))
    assert ok.status_code == 201 and client.get("/admin/submissions", headers=tenant_a).json()["total"] == 1


def test_idempotent_retry_is_stored_once(client, tenant_a, widget):
    headers = {"Idempotency-Key": "retry-key-12345"}
    first = client.post("/submissions", json=valid_submission(widget["id"]), headers=headers)
    second = client.post("/submissions", json=valid_submission(widget["id"]), headers=headers)
    assert first.status_code == 201 and second.status_code == 200 and second.json()["duplicate"] is True
    assert client.get("/admin/submissions", headers=tenant_a).json()["total"] == 1
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1          # one notification, not two


def test_migrations_are_idempotent_and_indexes_exist():
    db.migrate()
    db.migrate()
    with db.session() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        applied = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert {"idx_widgets_tenant", "idx_submissions_idem", "idx_submissions_tenant_time", "idx_jobs_due"} <= names
    assert applied == 1


def test_unexpected_routes_return_json_errors(client):
    r = client.get("/nope")
    assert r.status_code == 404 and r.json() == {"error": "Not Found"}
    assert client.delete("/submissions").status_code == 405
