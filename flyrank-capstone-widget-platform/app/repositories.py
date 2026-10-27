"""Data layer: SQL only, no business rules. Every widget/submission query is scoped by tenant_id."""
import json
import time


# ---- tenants ----
def create_tenant(conn, name, email, api_key_hash):
    cur = conn.execute(
        "INSERT INTO tenants (name, email, api_key_hash, created_at) VALUES (?, ?, ?, ?)",
        (name, email, api_key_hash, time.time()))
    return cur.lastrowid


def get_tenant_by_key_hash(conn, api_key_hash):
    return conn.execute("SELECT * FROM tenants WHERE api_key_hash = ?", (api_key_hash,)).fetchone()


def get_tenant(conn, tenant_id):
    return conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()


# ---- widgets ----
def insert_widget(conn, widget_id, tenant_id, data):
    now = time.time()
    conn.execute(
        """INSERT INTO widgets (id, tenant_id, type, title, description, fields_json, button_text,
                                success_message, version, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (widget_id, tenant_id, data["type"], data["title"], data["description"],
         json.dumps(data["fields"]), data["button_text"], data["success_message"], now, now))


def get_widget_for_tenant(conn, widget_id, tenant_id):
    # tenant_id in the WHERE clause is what makes tenant A unable to see tenant B's widget
    return conn.execute("SELECT * FROM widgets WHERE id = ? AND tenant_id = ?", (widget_id, tenant_id)).fetchone()


def get_widget_public(conn, widget_id):
    return conn.execute("SELECT * FROM widgets WHERE id = ?", (widget_id,)).fetchone()


def list_widgets(conn, tenant_id):
    return conn.execute("SELECT * FROM widgets WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,)).fetchall()


def update_widget(conn, widget_id, tenant_id, data):
    cur = conn.execute(
        """UPDATE widgets SET type = ?, title = ?, description = ?, fields_json = ?, button_text = ?,
                              success_message = ?, version = version + 1, updated_at = ?
           WHERE id = ? AND tenant_id = ?""",
        (data["type"], data["title"], data["description"], json.dumps(data["fields"]),
         data["button_text"], data["success_message"], time.time(), widget_id, tenant_id))
    return cur.rowcount > 0


def delete_widget(conn, widget_id, tenant_id):
    return conn.execute("DELETE FROM widgets WHERE id = ? AND tenant_id = ?", (widget_id, tenant_id)).rowcount > 0


# ---- submissions ----
def insert_submission(conn, widget_id, tenant_id, data_json, ip, geo, idempotency_key):
    geo = geo or {}
    cur = conn.execute(
        """INSERT INTO submissions (widget_id, tenant_id, data_json, ip, geo_country, geo_city, geo_provider,
                                    idempotency_key, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (widget_id, tenant_id, data_json, ip, geo.get("country"), geo.get("city"), geo.get("provider"),
         idempotency_key, time.time()))
    return cur.lastrowid


def find_submission_by_key(conn, widget_id, idempotency_key):
    return conn.execute("SELECT id FROM submissions WHERE widget_id = ? AND idempotency_key = ?",
                        (widget_id, idempotency_key)).fetchone()


def get_submission(conn, submission_id):
    return conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()


def list_submissions(conn, tenant_id, widget_id, limit, offset):
    where, params = "tenant_id = ?", [tenant_id]
    if widget_id:
        where += " AND widget_id = ?"
        params.append(widget_id)
    total = conn.execute(f"SELECT COUNT(*) FROM submissions WHERE {where}", params).fetchone()[0]
    rows = conn.execute(f"SELECT * FROM submissions WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                        params + [limit, offset]).fetchall()
    return rows, total


def stats(conn, tenant_id, since_epoch):
    total = conn.execute("SELECT COUNT(*) FROM submissions WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
    per_widget = conn.execute(
        """SELECT w.id AS widget_id, w.title AS title, COUNT(s.id) AS submissions
           FROM widgets w LEFT JOIN submissions s ON s.widget_id = w.id
           WHERE w.tenant_id = ? GROUP BY w.id ORDER BY submissions DESC, w.title""", (tenant_id,)).fetchall()
    by_day = conn.execute(
        """SELECT date(created_at, 'unixepoch') AS day, COUNT(*) AS submissions
           FROM submissions WHERE tenant_id = ? AND created_at >= ? GROUP BY day ORDER BY day""",
        (tenant_id, since_epoch)).fetchall()
    geo = conn.execute(
        """SELECT COALESCE(geo_country, 'unknown') AS country, COUNT(*) AS submissions
           FROM submissions WHERE tenant_id = ? GROUP BY country ORDER BY submissions DESC""", (tenant_id,)).fetchall()
    return total, per_widget, by_day, geo


# ---- background jobs ----
def enqueue_job(conn, job_type, payload):
    now = time.time()
    conn.execute("INSERT INTO jobs (type, payload_json, status, attempts, run_at, created_at) VALUES (?, ?, 'pending', 0, ?, ?)",
                 (job_type, json.dumps(payload), now, now))


def claim_due_job(conn, now):
    row = conn.execute("SELECT * FROM jobs WHERE status = 'pending' AND run_at <= ? ORDER BY id LIMIT 1", (now,)).fetchone()
    if row is None:
        return None
    # the status check in WHERE means only one worker can win this job
    claimed = conn.execute("UPDATE jobs SET status = 'running' WHERE id = ? AND status = 'pending'", (row["id"],)).rowcount
    return row if claimed else None


def finish_job(conn, job_id):
    conn.execute("UPDATE jobs SET status = 'done' WHERE id = ?", (job_id,))


def retry_job(conn, job_id, attempts, error, run_at):
    conn.execute("UPDATE jobs SET status = 'pending', attempts = ?, last_error = ?, run_at = ? WHERE id = ?",
                 (attempts, error[:500], run_at, job_id))


def fail_job(conn, job_id, attempts, error):
    conn.execute("UPDATE jobs SET status = 'failed', attempts = ?, last_error = ? WHERE id = ?",
                 (attempts, error[:500], job_id))


def requeue_stuck_jobs(conn):
    """A job left 'running' by a crash goes back to pending (at-least-once delivery)."""
    conn.execute("UPDATE jobs SET status = 'pending' WHERE status = 'running'")


def count_jobs(conn, status):
    return conn.execute("SELECT COUNT(*) FROM jobs WHERE status = ?", (status,)).fetchone()[0]
