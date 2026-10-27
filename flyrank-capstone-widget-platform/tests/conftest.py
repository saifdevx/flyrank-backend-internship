"""Tests use a throwaway database and a manual job runner, so every probe is deterministic."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update({
    "DATABASE_PATH": f"{_tmp}/test.db", "LOG_DIR": f"{_tmp}/logs", "WORKER_ENABLED": "0",
    "GEO_MODE": "mock", "DEV_TOOLS": "1", "PUBLIC_BASE_URL": "http://localhost:8000",
})

import pytest                                    # noqa: E402
from fastapi.testclient import TestClient        # noqa: E402

from app import config, db, dev_state, rate_limit   # noqa: E402
from app.main import app                          # noqa: E402

CONTACT_WIDGET = {
    "type": "contact_form", "title": "Contact us", "description": "Say hi",
    "fields": [{"name": "name", "label": "Name", "required": True},
               {"name": "email", "label": "Email", "type": "email", "required": True},
               {"name": "message", "label": "Message", "type": "textarea", "max_length": 100}],
    "button_text": "Send", "success_message": "Thanks!",
}


@pytest.fixture(autouse=True)
def clean_state():
    db.migrate()
    with db.session() as conn:
        conn.executescript("DELETE FROM submissions; DELETE FROM jobs; DELETE FROM widgets; DELETE FROM tenants;")
    dev_state.reset()
    rate_limit.limiter.reset()
    config.RATE_IP_BURST, config.RATE_IP_REFILL_PER_SEC = 1000, 1000     # generous unless a test lowers it
    config.RATE_WIDGET_BURST, config.RATE_WIDGET_REFILL_PER_SEC = 1000, 1000
    config.JOB_BACKOFF_SECONDS = 0
    yield


@pytest.fixture
def client():
    return TestClient(app)


def make_tenant(client, name="Acme", email="owner@acme.com"):
    r = client.post("/admin/tenants", json={"name": name, "email": email})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['api_key']}"}


@pytest.fixture
def tenant_a(client):
    return make_tenant(client, "A", "a@example.com")


@pytest.fixture
def tenant_b(client):
    return make_tenant(client, "B", "b@example.com")


@pytest.fixture
def widget(client, tenant_a):
    r = client.post("/admin/widgets", json=CONTACT_WIDGET, headers=tenant_a)
    assert r.status_code == 201, r.text
    return r.json()


def valid_submission(widget_id, **extra):
    body = {"widget_id": widget_id, "data": {"name": "Ada", "email": "ada@example.com", "message": "Hello"}}
    body.update(extra)
    return body
