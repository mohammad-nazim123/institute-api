"""
Notification API views.

POST /notifications/send-student-id/
    Body: { "student_id": <int>, "channel": "email" | "sms" | "both" }

POST /notifications/send-professor-id/
    Body: { "professor_id": <int>, "channel": "email" | "sms" | "both" }

POST /notifications/contact-us/
    Body: { "email": "<sender email>", "message": "<contact message>" }

The student/professor endpoints are protected by the x-admin-key header.
"""
import hmac
import json
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from students.models import Student
from professors.models import Professor

from .utils import send_contact_us_email, send_id_email, send_id_sms


# ──────────────────────────────────────
# Admin-key guard helper
# ──────────────────────────────────────

ADMIN_KEY = getattr(settings, "ADMIN_KEY", "")


def _check_admin_key(request):
    """Return None if authorised, else a 403 JsonResponse."""
    key = request.headers.get("x-admin-key", "")
    # Use constant-time comparison to prevent timing attacks
    if ADMIN_KEY and not hmac.compare_digest(str(key), str(ADMIN_KEY)):
        return JsonResponse({"error": "Unauthorized"}, status=403)
    return None


def _load_json_body(request):
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)


# ──────────────────────────────────────
# Public contact-us endpoint
# ──────────────────────────────────────

@csrf_exempt
@require_POST
def contact_us(request):
    """Send a contact-us message from the admin access modal to the support inbox."""
    data, error_response = _load_json_body(request)
    if error_response:
        return error_response

    email = data.get("email", "").strip()
    message = data.get("message", "").strip()

    if not email:
        return JsonResponse({"error": "'email' is required"}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "Enter a valid email address"}, status=400)

    if not message:
        return JsonResponse({"error": "'message' is required"}, status=400)
    if len(message) > 5000:
        return JsonResponse({"error": "'message' must be 5000 characters or fewer"}, status=400)

    result = send_contact_us_email(email, message)
    if result["success"]:
        return JsonResponse({"message": "Contact request sent successfully"}, status=200)

    return JsonResponse(
        {"error": "Failed to send contact request", "details": [result["error"]]},
        status=500,
    )


# ──────────────────────────────────────
# Student endpoint
# ──────────────────────────────────────

@csrf_exempt
@require_POST
def send_student_id(request):
    """Send a student's personal ID via email, SMS, or both."""
    auth_error = _check_admin_key(request)
    if auth_error:
        return auth_error

    data, error_response = _load_json_body(request)
    if error_response:
        return error_response

    personal_id = data.get("personal_id")
    channel = data.get("channel", "email").lower()
    payload_email = data.get("email", "").strip()
    payload_mobile = data.get("mobile", "").strip()

    if not personal_id:
        return JsonResponse({"error": "'personal_id' is required"}, status=400)

    if channel not in ("email", "sms", "both"):
        return JsonResponse({"error": "'channel' must be 'email', 'sms', or 'both'"}, status=400)

    # ── Fetch student details ──
    try:
        student = Student.objects.select_related('contact_details', 'system_details').get(
            system_details__student_personal_id=personal_id
        )
    except Student.DoesNotExist:
        return JsonResponse({"error": "Student not found with this personal ID"}, status=404)

    # ── Contact info ──
    contact = getattr(student, 'contact_details', None)
    if contact is None:
        return JsonResponse({"error": "Student contact details not found"}, status=404)

    results = []
    errors = []

    if channel in ("email", "both"):
        target_email = payload_email or contact.email
        if not target_email:
            errors.append("Student email is not set")
        else:
            result = send_id_email(target_email, personal_id, student.name, role="Student")
            if result["success"]:
                results.append("email")
            else:
                errors.append(f"Email failed: {result['error']}")

    if channel in ("sms", "both"):
        target_mobile = payload_mobile or contact.mobile
        if not target_mobile:
            errors.append("Student mobile number is not set")
        else:
            result = send_id_sms(target_mobile, personal_id, student.name)
            if result["success"]:
                results.append("sms")
            else:
                errors.append(f"SMS failed: {result['error']}")

    return _build_response(results, errors)


# ──────────────────────────────────────
# Professor endpoint
# ──────────────────────────────────────

@csrf_exempt
@require_POST
def send_professor_id(request):
    """Send a professor's personal ID via email, SMS, or both."""
    auth_error = _check_admin_key(request)
    if auth_error:
        return auth_error

    data, error_response = _load_json_body(request)
    if error_response:
        return error_response

    personal_id = data.get("personal_id")
    channel = data.get("channel", "email").lower()
    payload_email = data.get("email", "").strip()
    payload_mobile = data.get("mobile", "").strip()

    if not personal_id:
        return JsonResponse({"error": "'personal_id' is required"}, status=400)

    if channel not in ("email", "sms", "both"):
        return JsonResponse({"error": "'channel' must be 'email', 'sms', or 'both'"}, status=400)

    # ── Fetch professor details ──
    try:
        professor = Professor.objects.select_related('admin_employement').get(
            admin_employement__personal_id=personal_id
        )
    except Professor.DoesNotExist:
        return JsonResponse({"error": "Professor not found with this personal ID"}, status=404)

    results = []
    errors = []

    if channel in ("email", "both"):
        target_email = payload_email or professor.email
        if not target_email:
            errors.append("Professor email is not set")
        else:
            result = send_id_email(target_email, personal_id, professor.name, role="Professor")
            if result["success"]:
                results.append("email")
            else:
                errors.append(f"Email failed: {result['error']}")

    if channel in ("sms", "both"):
        target_mobile = payload_mobile or professor.phone_number
        if not target_mobile:
            errors.append("Professor phone number is not set")
        else:
            result = send_id_sms(target_mobile, personal_id, professor.name)
            if result["success"]:
                results.append("sms")
            else:
                errors.append(f"SMS failed: {result['error']}")

    return _build_response(results, errors)


# ──────────────────────────────────────
# Shared response builder
# ──────────────────────────────────────

def _build_response(results: list, errors: list) -> JsonResponse:
    if results and not errors:
        return JsonResponse(
            {"message": f"Personal ID sent successfully via {', '.join(results)}"},
            status=200,
        )
    if results and errors:
        # Partial success
        return JsonResponse(
            {
                "message": f"Personal ID sent via {', '.join(results)}",
                "warnings": errors,
            },
            status=207,
        )
    # Total failure
    return JsonResponse({"error": "Failed to send personal ID", "details": errors}, status=500)
