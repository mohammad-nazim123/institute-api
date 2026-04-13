import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

FULL_ACCESS_CONTROL = 'full access'
ADMIN_ACCESS_CONTROL = 'admin access'
STUDENT_ACCESS_CONTROL = 'student access'
FEE_ACCESS_CONTROL = 'fee access'


def get_request_institute_id(request):
    institute_id = request.query_params.get('institute')
    if not institute_id and hasattr(request, 'data'):
        institute_id = request.data.get('institute')
    return institute_id


def get_request_admin_key(request):
    return (
        request.headers.get('X-Admin-Key')
        or request.query_params.get('admin_key')
    )


def normalize_access_control(value):
    return ' '.join(str(value or '').strip().lower().split())


def get_allowed_subordinate_access_controls(view=None, explicit=None):
    raw_values = explicit
    if raw_values is None and view is not None:
        raw_values = getattr(view, 'allowed_subordinate_access_controls', ())

    if isinstance(raw_values, str):
        raw_values = (raw_values,)

    return {
        normalized
        for normalized in (
            normalize_access_control(value)
            for value in (raw_values or ())
        )
        if normalized
    }


def get_verified_institute(request):
    from iinstitutes_list.models import Institute

    institute_id = get_request_institute_id(request)
    if not institute_id:
        raise PermissionDenied('Institute id is required.')

    try:
        institute = Institute.objects.only(
            'id',
            'admin_key',
            'event_status',
            'institute_name',
            'super_admin_name',
        ).get(pk=institute_id)
    except Institute.DoesNotExist:
        raise PermissionDenied('Institute not found.')

    if institute.event_status != 'active':
        raise PermissionDenied(
            f'Institute events are currently {institute.event_status}. Access denied.'
        )

    return institute


def cache_verified_admin_request(request, institute, admin_key, subordinate=None):
    request._verified_institute = institute
    request._admin_key = admin_key

    if subordinate is None:
        request._verified_subordinate_access = None
        request._verified_access_control = FULL_ACCESS_CONTROL
        request._verified_actor_role = 'Super Admin'
        request._verified_actor_name = getattr(institute, 'super_admin_name', '')
        return

    request._verified_subordinate_access = subordinate
    request._verified_access_control = normalize_access_control(subordinate.access_control)
    request._verified_actor_role = subordinate.post
    request._verified_actor_name = subordinate.name


def verify_admin_key_for_institute(
    request,
    institute,
    *,
    view=None,
    message='Invalid or missing admin key for this institute.',
    admin_key=None,
    allowed_subordinate_access_controls=None,
):
    from subordinate_access.models import SubordinateAccess

    resolved_admin_key = admin_key if admin_key is not None else get_request_admin_key(request)

    if not resolved_admin_key:
        raise PermissionDenied('Admin key is required (X-Admin-Key header or admin_key query param).')

    if hmac.compare_digest(str(institute.admin_key or ''), str(resolved_admin_key)):
        cache_verified_admin_request(request, institute, resolved_admin_key)
        return True

    allowed_controls = get_allowed_subordinate_access_controls(
        view=view,
        explicit=allowed_subordinate_access_controls,
    )
    if not allowed_controls:
        raise PermissionDenied(message)

    subordinate = (
        SubordinateAccess.objects
        .filter(
            institute=institute,
            access_code=resolved_admin_key,
            is_active=True,
        )
        .only(
            'id',
            'institute_id',
            'post',
            'name',
            'access_control',
            'access_code',
            'is_active',
        )
        .first()
    )
    if subordinate is None:
        raise PermissionDenied(message)

    subordinate_access_control = normalize_access_control(subordinate.access_control)
    if subordinate_access_control not in allowed_controls:
        raise PermissionDenied(message)

    cache_verified_admin_request(request, institute, resolved_admin_key, subordinate=subordinate)
    return True





class InstituteKeyPermission(BasePermission):
    """
    Checks that the request carries a valid admin_key for the institute being accessed.

    The client must send:
      - institute id:  query param `?institute=<id>`  OR in the request body as `institute`
      - admin key:     header `X-Admin-Key: <key>`    OR query param `?admin_key=<key>`

    Returns 403 if the key is missing or does not match the institute's admin_key.
    """
    message = 'Invalid or missing admin key for this institute.'

    def has_permission(self, request, view):
        institute = get_verified_institute(request)
        verify_admin_key_for_institute(
            request,
            institute,
            view=view,
            message=self.message,
        )
        return True


class SuperAdminKeyPermission(BasePermission):
    """
    Protects global super-admin resources with the configured 32-character
    X-Admin-Key header only.

    We intentionally do not accept query parameters for this key so sensitive
    values are less likely to leak via browser history or logs.
    """

    message = 'You do not have permission to access this resource.'

    def has_permission(self, request, view):
        configured_key = getattr(settings, 'ADMIN_KEY', '') or ''
        provided_key = request.headers.get('X-Admin-Key') or ''

        if len(configured_key) != 32:
            raise PermissionDenied(self.message)

        if len(provided_key) != 32:
            raise PermissionDenied(self.message)

        if not hmac.compare_digest(provided_key, configured_key):
            raise PermissionDenied(self.message)

        request._super_admin_authenticated = True
        return True


class PersonalKeyPermission(BasePermission):
    """
    Used for retrieve (GET by ID) on Student and Professor ViewSets.

    The client must send:
      - header `X-Personal-Key: <personal-id>`

    Verifies the key matches the specific object's personal_id and
    that the institute's event_status is active.

    The VIEW must check has_object_permission after fetching the object,
    because we cannot check the personal_id at has_permission time
    (we don't have the object yet). We allow has_permission to pass
    and do the real check in has_object_permission.
    """
    message = 'Invalid or missing personal key.'

    def has_permission(self, request, view):
        # We just ensure the header is present; real check is in has_object_permission
        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key')
        if not personal_key:
            raise PermissionDenied('Personal key is required (X-Personal-Key header).')
        # Store for use in has_object_permission
        request._personal_key = personal_key
        return True

    def has_object_permission(self, request, view, obj):
        personal_key = getattr(request, '_personal_key', None)
        if not personal_key:
            raise PermissionDenied(self.message)

        # Determine which personal_id field to check based on model
        from students.models import Student
        from professors.models import Professor

        if isinstance(obj, Student):
            try:
                expected_key = obj.system_details.student_personal_id
            except Exception:
                raise PermissionDenied('Student system details not found.')
        elif isinstance(obj, Professor):
            try:
                expected_key = obj.admin_employement.personal_id
            except Exception:
                raise PermissionDenied('Professor admin employment details not found.')
        else:
            raise PermissionDenied('Unsupported object type for personal key check.')

        if personal_key != expected_key:
            raise PermissionDenied(self.message)

        # Also check institute event status
        if obj.institute and obj.institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {obj.institute.event_status}. Access denied.'
            )

        return True


class StudentPersonalKeyPermission(BasePermission):
    """
    Used for student retrieve (GET by ID).

    The client must send:
      - header `X-Personal-Key: <15-char-student-personal-id>`
    """
    message = 'Invalid or missing student personal key.'

    def has_permission(self, request, view):
        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key')
        if not personal_key:
            raise PermissionDenied('Student personal key is required (X-Personal-Key header).')
        if len(personal_key) != 15:
            raise PermissionDenied('Student personal key must be exactly 15 characters.')
        request._personal_key = personal_key
        return True

    def has_object_permission(self, request, view, obj):
        from students.models import Student

        personal_key = getattr(request, '_personal_key', None)
        if not personal_key:
            raise PermissionDenied(self.message)
        if not isinstance(obj, Student):
            raise PermissionDenied('Unsupported object type for student personal key check.')

        try:
            expected_key = obj.system_details.student_personal_id
        except Exception:
            raise PermissionDenied('Student system details not found.')

        if personal_key != expected_key:
            raise PermissionDenied(self.message)

        if obj.institute and obj.institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {obj.institute.event_status}. Access denied.'
            )

        return True


class StudentRetrievePermission(BasePermission):
    """
    Allows student detail access via either:
      - X-Admin-Key    header: institute admin/subordinate key
      - X-Personal-Key header: 15-char student personal ID

    Admin-key access is resolved against the retrieved student's institute, so
    the client does not need to send ?institute=<id> for detail routes.
    """
    message = 'Provide X-Admin-Key or X-Personal-Key (student personal ID).'

    def has_permission(self, request, view):
        request._student_retrieve_admin_key = get_request_admin_key(request)
        request._student_retrieve_personal_key = (
            request.headers.get('X-Personal-Key')
            or request.query_params.get('personal_key')
        )

        if not request._student_retrieve_admin_key and not request._student_retrieve_personal_key:
            raise PermissionDenied(self.message)

        return True

    def has_object_permission(self, request, view, obj):
        from students.models import Student

        if not isinstance(obj, Student):
            raise PermissionDenied('Unsupported object type for student detail access.')

        if obj.institute and obj.institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {obj.institute.event_status}. Access denied.'
            )

        admin_key = getattr(request, '_student_retrieve_admin_key', None)
        personal_key = getattr(request, '_student_retrieve_personal_key', None)

        if admin_key:
            try:
                verify_admin_key_for_institute(
                    request,
                    obj.institute,
                    view=view,
                    message='Invalid admin key for this institute.',
                    admin_key=admin_key,
                )
                return True
            except PermissionDenied:
                if not personal_key:
                    raise

        if not personal_key:
            raise PermissionDenied(self.message)

        if len(personal_key) != 15:
            raise PermissionDenied('Student personal key must be exactly 15 characters.')

        try:
            expected_key = obj.system_details.student_personal_id
        except Exception:
            raise PermissionDenied('Student system details not found.')

        if personal_key != expected_key:
            raise PermissionDenied('Invalid or missing student personal key.')

        request._verified_student = obj
        return True


class ProfessorRetrievePermission(BasePermission):
    """
    Allows professor detail access via either:
      - X-Admin-Key    header: institute admin/subordinate key
      - X-Personal-Key header: professor personal ID

    Admin-key access is resolved against the retrieved professor's institute, so
    the client does not need to send ?institute=<id> for detail routes.
    """
    message = 'Provide X-Admin-Key or X-Personal-Key (professor personal ID).'

    def has_permission(self, request, view):
        request._professor_retrieve_admin_key = get_request_admin_key(request)
        request._professor_retrieve_personal_key = (
            request.headers.get('X-Personal-Key')
            or request.query_params.get('personal_key')
        )

        if (
            not request._professor_retrieve_admin_key
            and not request._professor_retrieve_personal_key
        ):
            raise PermissionDenied(self.message)

        return True

    def has_object_permission(self, request, view, obj):
        from professors.models import Professor

        if not isinstance(obj, Professor):
            raise PermissionDenied('Unsupported object type for professor detail access.')

        if obj.institute and obj.institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {obj.institute.event_status}. Access denied.'
            )

        admin_key = getattr(request, '_professor_retrieve_admin_key', None)
        personal_key = getattr(request, '_professor_retrieve_personal_key', None)

        if admin_key:
            try:
                verify_admin_key_for_institute(
                    request,
                    obj.institute,
                    view=view,
                    message='Invalid admin key for this institute.',
                    admin_key=admin_key,
                )
                request._verified_institute = obj.institute
                return True
            except PermissionDenied:
                if not personal_key:
                    raise

        if not personal_key:
            raise PermissionDenied(self.message)

        try:
            expected_key = obj.admin_employement.personal_id
        except Exception:
            raise PermissionDenied('Professor admin employment details not found.')

        if personal_key != expected_key:
            raise PermissionDenied('Invalid or missing professor personal key.')

        request._verified_institute = obj.institute
        request._verified_professor = obj
        return True


class AttendancePermission(BasePermission):
    """
    Allows access to Attendance endpoints via EITHER:
      - X-Admin-Key   header: 32-hex-char admin key
      - X-Personal-Key header: professor personal ID

    The institute must be identified by ?institute=<id> or body field `institute`.
    On success, sets:
      - request._verified_institute
      - request._verified_professor  (only when authenticated via personal key)
    """

    message = 'Invalid or missing key. Provide X-Admin-Key for institute access or X-Personal-Key (professor personal ID).'

    def _get_institute_id(self, request):
        return get_request_institute_id(request)

    def has_permission(self, request, view):
        from professors.models import professorAdminEmployement

        admin_key = request.headers.get('X-Admin-Key') or request.query_params.get('admin_key')
        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key')

        if not admin_key and not personal_key:
            raise PermissionDenied(
                'Provide X-Admin-Key for institute access or X-Personal-Key (professor personal ID).'
            )

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (query param ?institute= or body field).')

        institute = get_verified_institute(request)

        # --- Try admin key first ---
        if admin_key:
            try:
                verify_admin_key_for_institute(
                    request,
                    institute,
                    view=view,
                    message='Invalid admin key for this institute.',
                    admin_key=admin_key,
                )
                return True
            except PermissionDenied:
                if not personal_key:
                    raise

        # --- Try professor personal key ---
        if personal_key:
            try:
                prof_employment = professorAdminEmployement.objects.select_related(
                    'professor__institute'
                ).get(personal_id=personal_key)
            except professorAdminEmployement.DoesNotExist:
                raise PermissionDenied('No professor found with the given personal key.')

            if prof_employment.professor.institute_id != institute.id:
                raise PermissionDenied('Professor personal key does not belong to this institute.')

            request._verified_institute = institute
            request._verified_professor = prof_employment.professor
            return True

        raise PermissionDenied(self.message)


class SchedulePermission(BasePermission):
    """
    Allows access to Schedule (weekly & exam) endpoints via ANY of:
      - X-Admin-Key    header: 32-char admin key     → full CRUD
      - X-Personal-Key header: professor personal ID → full CRUD
      - X-Personal-Key header: student personal ID   → GET (read-only)

    The institute must be identified by ?institute=<id> or body field `institute`.
    On success sets one of:
      - request._verified_institute
      - request._verified_professor  (professor key)
      - request._verified_student    (student key)

    Write operations (POST/PUT/PATCH/DELETE) via student key are rejected with 403.
    """

    message = (
        'Provide X-Admin-Key or X-Personal-Key '
        '(professor or student personal ID).'
    )

    def _get_institute_id(self, request):
        return get_request_institute_id(request)

    def has_permission(self, request, view):
        from students.models import StudentSystemDetails
        from professors.models import professorAdminEmployement

        admin_key   = request.headers.get('X-Admin-Key')   or request.query_params.get('admin_key')
        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key')

        if not admin_key and not personal_key:
            raise PermissionDenied(self.message)

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (?institute= query param or body field).')

        institute = get_verified_institute(request)

        # ── 1. Admin key ─────────────────────────────────────────────────────
        if admin_key:
            try:
                verify_admin_key_for_institute(
                    request,
                    institute,
                    view=view,
                    message='Invalid admin key for this institute.',
                    admin_key=admin_key,
                )
                return True
            except PermissionDenied:
                if not personal_key:
                    raise

        # ── 2. Personal key — try professor first, then student ───────────────
        if personal_key:
            is_read_only = request.method in ('GET', 'HEAD', 'OPTIONS')

            # 2a. Professor key
            try:
                prof_employment = professorAdminEmployement.objects.select_related(
                    'professor__institute'
                ).get(personal_id=personal_key)

                if prof_employment.professor.institute_id != institute.id:
                    raise PermissionDenied('Professor personal key does not belong to this institute.')

                request._verified_institute = institute
                request._verified_professor = prof_employment.professor
                return True

            except professorAdminEmployement.DoesNotExist:
                pass  # not a professor key — try student

            # 2b. Student key (read-only)
            try:
                system_details = StudentSystemDetails.objects.select_related(
                    'student__institute'
                ).get(student_personal_id=personal_key)

                if system_details.student.institute_id != institute.id:
                    raise PermissionDenied('Student personal key does not belong to this institute.')

                if not is_read_only:
                    raise PermissionDenied('Students can only read schedules. Write operations require X-Admin-Key.')

                request._verified_institute = institute
                request._verified_student = system_details.student
                return True

            except StudentSystemDetails.DoesNotExist:
                pass  # key not found in either table

            raise PermissionDenied('No professor or student found with the given personal key.')

        raise PermissionDenied(self.message)


class SubjectAssignmentPermission(BasePermission):
    """
    Allows SubjectAssigned access via:
      - X-Admin-Key    header: 32-char admin key     → full CRUD
      - X-Personal-Key header: student personal ID   → GET only

    The institute must be identified by ?institute=<id> or body field `institute`.
    On success sets:
      - request._verified_institute
      - request._verified_student  (student key)
    """

    message = 'Provide X-Admin-Key or X-Personal-Key (student personal ID).'

    def _get_institute_id(self, request):
        return get_request_institute_id(request)

    def has_permission(self, request, view):
        from students.models import StudentSystemDetails

        admin_key = request.headers.get('X-Admin-Key') or request.query_params.get('admin_key')
        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key')

        if not admin_key and not personal_key:
            raise PermissionDenied(self.message)

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (?institute= query param or body field).')

        institute = get_verified_institute(request)

        if admin_key:
            try:
                verify_admin_key_for_institute(
                    request,
                    institute,
                    view=view,
                    message='Invalid admin key for this institute.',
                    admin_key=admin_key,
                )
                return True
            except PermissionDenied:
                if not personal_key:
                    raise

        if personal_key:
            is_read_only = request.method in ('GET', 'HEAD', 'OPTIONS')

            try:
                system_details = StudentSystemDetails.objects.select_related(
                    'student__institute'
                ).get(student_personal_id=personal_key)
            except StudentSystemDetails.DoesNotExist:
                raise PermissionDenied('No student found with the given personal key.')

            if system_details.student.institute_id != institute.id:
                raise PermissionDenied('Student personal key does not belong to this institute.')

            if not is_read_only:
                raise PermissionDenied('Students can only read subject assignments. Write operations require X-Admin-Key.')

            request._verified_institute = institute
            request._verified_student = system_details.student
            return True

        raise PermissionDenied(self.message)
