"""The side effect: tell the tenant about a new lead. Run by the background worker, so it can fail harmlessly."""
from . import dev_state


def send_new_lead_notification(tenant_email, widget_title, submission_id):
    if dev_state.get()["email_fail"]:
        raise RuntimeError("email provider unavailable (forced by dev toggle)")
    # Console "email". Swapping in smtplib / Mailpit would only change this function.
    print(f"EMAIL -> {tenant_email}: new lead #{submission_id} on widget '{widget_title}'", flush=True)
