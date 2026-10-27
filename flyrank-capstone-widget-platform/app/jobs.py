"""Background worker: takes jobs off the table, retries failures with backoff, raises an alert when it gives up."""
import json
import logging
import threading
import time
from datetime import datetime, timezone

from . import config, db, notify, repositories as repo

log = logging.getLogger("worker")


def handle_job(job):
    payload = json.loads(job["payload_json"])
    if job["type"] != "notify_new_submission":
        raise ValueError(f"unknown job type {job['type']}")
    with db.session() as conn:
        sub = repo.get_submission(conn, payload["submission_id"])
        widget = repo.get_widget_public(conn, sub["widget_id"])
        tenant = repo.get_tenant(conn, sub["tenant_id"])
    notify.send_new_lead_notification(tenant["email"], widget["title"], sub["id"])


def alert(job, attempts, error):
    """Failure alert. In production this would page someone; here it is a loud log line plus logs/alerts.log."""
    line = f"{datetime.now(timezone.utc).isoformat()} ALERT job {job['id']} ({job['type']}) failed after {attempts} attempts: {error}"
    log.error(line)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.LOG_DIR / "alerts.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def process_one():
    """Run one due job. Returns True if a job was processed."""
    with db.session() as conn:
        job = repo.claim_due_job(conn, time.time())
    if job is None:
        return False
    try:
        handle_job(job)
    except Exception as e:
        attempts = job["attempts"] + 1
        with db.session() as conn:
            if attempts >= config.JOB_MAX_ATTEMPTS:
                repo.fail_job(conn, job["id"], attempts, str(e))
            else:
                delay = config.JOB_BACKOFF_SECONDS * (2 ** (attempts - 1))
                repo.retry_job(conn, job["id"], attempts, str(e), time.time() + delay)
        if attempts >= config.JOB_MAX_ATTEMPTS:
            alert(job, attempts, e)
    else:
        with db.session() as conn:
            repo.finish_job(conn, job["id"])
    return True


class Worker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        with db.session() as conn:
            repo.requeue_stuck_jobs(conn)
        self._thread = threading.Thread(target=self._run, name="job-worker", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self):
        while not self._stop.is_set():
            try:
                did_work = process_one()
            except Exception:
                log.exception("worker loop error")
                did_work = False
            if not did_work:
                self._stop.wait(config.JOB_POLL_SECONDS)
