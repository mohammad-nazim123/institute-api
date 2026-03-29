"""
Notification helper utilities: email (Django SMTP) + SMS (Twilio).
"""
from django.core.mail import send_mail
from django.conf import settings


# ──────────────────────────────────────
# Email
# ──────────────────────────────────────

def send_id_email(to_email: str, personal_id: str, name: str, role: str = "Member") -> dict:
    """
    Send personal ID to the given email address.
    Returns {"success": True} or {"success": False, "error": str}.
    """
    subject = "Your Personal ID – Institute Notification"
    message = (
        f"Dear {name},\n\n"
        f"Your email ID is: {to_email}\n\n\n"
        f"Your personal ID is: {personal_id}\n\n\n"
        f"Use your email and this ID to login into the institute portal.\nPlease keep this ID confidential and do not share it with anyone.\n\n"
        f"Regards,\nInstitute Administration"
    )
    default_from = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    if not default_from:
        default_from = "noreply@institute.com"

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=default_from,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ──────────────────────────────────────
# SMS  (Twilio)
# ──────────────────────────────────────

def send_id_sms(to_number: str, personal_id: str, name: str) -> dict:
    """
    Send personal ID via SMS using Twilio.
    Returns {"success": True} or {"success": False, "error": str}.
    If Twilio credentials are not configured, returns a graceful skip.
    """
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token  = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", "")

    if not all([account_sid, auth_token, from_number]):
        return {"success": False, "error": "Twilio credentials not configured"}

    try:
        from twilio.rest import Client  # imported lazily so it won't break if not installed
        client = Client(account_sid, auth_token)
        body = (
            f"Dear {name}, your Institute Personal ID is: {personal_id}. "
            f"Please keep it confidential."
        )
        # Ensure the number starts with '+'
        if to_number and not to_number.startswith("+"):
            to_number = "+" + to_number

        client.messages.create(body=body, from_=from_number, to=to_number)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
