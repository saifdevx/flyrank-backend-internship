"""Demo data: two tenants (so isolation can be shown) and one widget each.   Run: python -m app.seed"""
import json
import os
import secrets

from . import config, db, repositories as repo, security, services
from .schemas import FieldDef, WidgetIn

KEYS_FILE = config.ROOT / "data" / "demo-keys.json"


def demo_key(name):
    """Env var wins; otherwise generate once and remember in data/demo-keys.json (git-ignored)."""
    env_value = os.getenv(f"DEMO_KEY_{name.upper()}")
    if env_value:
        return env_value
    saved = json.loads(KEYS_FILE.read_text()) if KEYS_FILE.exists() else {}
    if name not in saved:
        saved[name] = "fr_demo_" + secrets.token_urlsafe(18)
        KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEYS_FILE.write_text(json.dumps(saved, indent=2))
    return saved[name]


def ensure_tenant(name, email, api_key):
    with db.session() as conn:
        tenant = repo.get_tenant_by_key_hash(conn, security.hash_key(api_key))
        if tenant:
            return tenant["id"]
        return repo.create_tenant(conn, name, email, security.hash_key(api_key))


def ensure_widget(tenant_id, widget_id, payload):
    with db.session() as conn:
        if repo.get_widget_public(conn, widget_id):
            return
    services.create_widget(tenant_id, payload, widget_id=widget_id)


def main():
    db.migrate()
    key_a, key_b = demo_key("a"), demo_key("b")
    tenant_a = ensure_tenant("Demo Tenant A", "owner-a@example.com", key_a)
    tenant_b = ensure_tenant("Demo Tenant B", "owner-b@example.com", key_b)

    ensure_widget(tenant_a, "demo-contact-a", WidgetIn(
        type="contact_form", title="Contact us", description="We usually reply within a day.",
        fields=[FieldDef(name="name", label="Your name", required=True),
                FieldDef(name="email", label="Email", type="email", required=True),
                FieldDef(name="message", label="Message", type="textarea", max_length=1000)],
        button_text="Send", success_message="Thanks! We'll be in touch."))
    ensure_widget(tenant_b, "demo-signup-b", WidgetIn(
        type="signup_form", title="Join the newsletter", description="One email a month.",
        fields=[FieldDef(name="email", label="Email", type="email", required=True)],
        button_text="Subscribe", success_message="You're on the list!"))

    print("Seeded demo data.\n")
    print(f"Tenant A  API key: {key_a}   widget: demo-contact-a")
    print(f"Tenant B  API key: {key_b}   widget: demo-signup-b")
    print(f"\nEmbed snippet A: {services.embed_snippet(tenant_a, 'demo-contact-a')['snippet']}")
    print("Use the key as:  Authorization: Bearer <key>")


if __name__ == "__main__":
    main()
