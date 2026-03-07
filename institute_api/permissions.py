from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied





class InstituteKeyPermission(BasePermission):
    """
    Checks that the request carries a valid admin_key for the institute being accessed.

    The client must send:
      - institute id:  query param `?institute=<id>`  OR in the request body as `institute`
      - admin key:     header `X-Admin-Key: <key>`    OR query param `?admin_key=<key>`

    Returns 403 if the key is missing or does not match the institute's admin_key.
    """
    message = 'Invalid or missing admin key for this institute.'

    def _get_institute_id(self, request):
        institute_id = request.query_params.get('institute')
        if not institute_id and hasattr(request, 'data'):
            institute_id = request.data.get('institute')
        return institute_id

    def _get_admin_key(self, request):
        # Accept header (preferred) or query param (fallback)
        return (
            request.headers.get('X-Admin-Key')
            or request.query_params.get('admin_key')
        )

    def has_permission(self, request, view):
        from iinstitutes_list.models import Institute

        institute_id = self._get_institute_id(request)
        admin_key = self._get_admin_key(request)

        if not institute_id:
            raise PermissionDenied('Institute id is required.')

        if not admin_key:
            raise PermissionDenied('Admin key is required (X-Admin-Key header or admin_key query param).')

        try:
            institute = Institute.objects.get(pk=institute_id)
        except Institute.DoesNotExist:
            raise PermissionDenied('Institute not found.')

        if institute.admin_key != admin_key:
            raise PermissionDenied(self.message)

        # Block access if the institute's events are paused or stopped
        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        # Cache the verified institute on the request for use by the view
        request._verified_institute = institute
        return True


class PersonalKeyPermission(BasePermission):
    """
    Used for retrieve (GET by ID) on Student and Professor ViewSets.

    The client must send:
      - header `X-Personal-Key: <16-digit-personal-id>`

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


class AttendancePermission(BasePermission):
    """
    Allows access to Attendance endpoints via EITHER:
      - X-Admin-Key   header: 32-hex-char admin key
      - X-Personal-Key header: 15-digit professor personal ID

    The institute must be identified by ?institute=<id> or body field `institute`.
    On success, sets:
      - request._verified_institute
      - request._verified_professor  (only when authenticated via personal key)
    """

    message = 'Invalid or missing key. Provide X-Admin-Key (32 chars) or X-Personal-Key (15-digit professor ID).'

    def _get_institute_id(self, request):
        return (
            request.query_params.get('institute')
            or (request.data.get('institute') if hasattr(request, 'data') else None)
        )

    def has_permission(self, request, view):
        from iinstitutes_list.models import Institute
        from professors.models import professorAdminEmployement

        admin_key = request.headers.get('X-Admin-Key') or request.query_params.get('admin_key')
        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key')

        if not admin_key and not personal_key:
            raise PermissionDenied(
                'Provide X-Admin-Key (32-char admin key) or X-Personal-Key (15-digit professor ID).'
            )

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (query param ?institute= or body field).')

        try:
            institute = Institute.objects.get(pk=institute_id)
        except Institute.DoesNotExist:
            raise PermissionDenied('Institute not found.')

        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        # --- Try admin key first ---
        if admin_key:
            if admin_key == institute.admin_key:
                request._verified_institute = institute
                return True
            if not personal_key:
                raise PermissionDenied('Invalid admin key for this institute.')

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
      - X-Personal-Key header: professor 15-char ID  → full CRUD
      - X-Personal-Key header: student 15-char ID    → GET (read-only)

    The institute must be identified by ?institute=<id> or body field `institute`.
    On success sets one of:
      - request._verified_institute
      - request._verified_professor  (professor key)
      - request._verified_student    (student key)

    Write operations (POST/PUT/PATCH/DELETE) via student key are rejected with 403.
    """

    message = (
        'Provide X-Admin-Key (32-char) or X-Personal-Key '
        '(15-char professor or student ID).'
    )

    def _get_institute_id(self, request):
        return (
            request.query_params.get('institute')
            or (request.data.get('institute') if hasattr(request, 'data') else None)
        )

    def has_permission(self, request, view):
        from iinstitutes_list.models import Institute
        from students.models import StudentSystemDetails
        from professors.models import professorAdminEmployement

        admin_key   = request.headers.get('X-Admin-Key')   or request.query_params.get('admin_key')
        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key')

        if not admin_key and not personal_key:
            raise PermissionDenied(self.message)

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (?institute= query param or body field).')

        try:
            institute = Institute.objects.get(pk=institute_id)
        except Institute.DoesNotExist:
            raise PermissionDenied('Institute not found.')

        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        # ── 1. Admin key ─────────────────────────────────────────────────────
        if admin_key:
            if admin_key == institute.admin_key:
                request._verified_institute = institute
                return True
            if not personal_key:
                raise PermissionDenied('Invalid admin key for this institute.')

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

