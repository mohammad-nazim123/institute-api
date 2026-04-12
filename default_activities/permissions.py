import hmac

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from institute_api.permissions import (
    cache_verified_admin_request,
    get_request_admin_key,
    get_verified_institute,
)


class DefaultActivityPermission(BasePermission):
    message = (
        'Read access requires a 29, 30, 31, or 32 character institute key '
        'or a 15 character personal key. Write access requires the exact '
        '32 character institute admin key.'
    )
    read_access_key_lengths = {29, 30, 31, 32}

    def has_permission(self, request, view):
        institute = get_verified_institute(request)

        if request.method in SAFE_METHODS:
            return self._has_read_permission(request, institute)

        return self._has_write_permission(request, institute)

    def _has_write_permission(self, request, institute):
        admin_key = get_request_admin_key(request) or ''

        if len(admin_key) != 32:
            raise PermissionDenied(
                'Create, edit, update, and delete require the exact 32 character admin key.'
            )

        if not hmac.compare_digest(str(institute.admin_key or ''), str(admin_key)):
            raise PermissionDenied(
                'Create, edit, update, and delete require the exact 32 character admin key.'
            )

        cache_verified_admin_request(request, institute, admin_key)
        return True

    def _has_read_permission(self, request, institute):
        admin_key = get_request_admin_key(request)
        personal_key = (
            request.headers.get('X-Personal-Key')
            or request.query_params.get('personal_key')
        )

        if admin_key and len(str(admin_key)) == 15 and not personal_key:
            personal_key = admin_key
            admin_key = None

        if not admin_key and not personal_key:
            raise PermissionDenied(self.message)

        if admin_key:
            if len(str(admin_key)) not in self.read_access_key_lengths:
                raise PermissionDenied(
                    'Provide X-Admin-Key with 29, 30, 31, or 32 characters for read access.'
                )

            if self._grant_institute_key_access(request, institute, admin_key):
                return True

            if not personal_key:
                raise PermissionDenied('Invalid institute access key for this institute.')

        if personal_key:
            return self._grant_personal_key_access(request, institute, personal_key)

        raise PermissionDenied(self.message)

    def _grant_institute_key_access(self, request, institute, admin_key):
        if hmac.compare_digest(str(institute.admin_key or ''), str(admin_key)):
            cache_verified_admin_request(request, institute, admin_key)
            return True

        from subordinate_access.models import SubordinateAccess

        subordinate = (
            SubordinateAccess.objects
            .filter(
                institute=institute,
                access_code=admin_key,
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
            return False

        cache_verified_admin_request(request, institute, admin_key, subordinate=subordinate)
        return True

    def _grant_personal_key_access(self, request, institute, personal_key):
        if len(str(personal_key)) != 15:
            raise PermissionDenied('Provide a personal key with exactly 15 characters.')

        from professors.models import professorAdminEmployement
        from published_professors.models import PublishedProfessor
        from students.models import StudentSystemDetails

        student_details = (
            StudentSystemDetails.objects
            .select_related('student')
            .filter(
                student__institute_id=institute.id,
                student_personal_id=personal_key,
            )
            .first()
        )
        if student_details is not None:
            request._verified_institute = institute
            request._personal_key = personal_key
            request._verified_student = student_details.student
            return True

        professor_employment = (
            professorAdminEmployement.objects
            .select_related('professor')
            .filter(
                professor__institute_id=institute.id,
                personal_id=personal_key,
            )
            .first()
        )
        if professor_employment is not None:
            request._verified_institute = institute
            request._personal_key = personal_key
            request._verified_professor = professor_employment.professor
            return True

        published_professor = (
            PublishedProfessor.objects
            .filter(
                institute_id=institute.id,
                professor_personal_id=personal_key,
            )
            .only('id', 'institute_id', 'professor_personal_id')
            .first()
        )
        if published_professor is not None:
            request._verified_institute = institute
            request._personal_key = personal_key
            request._verified_published_professor = published_professor
            return True

        raise PermissionDenied('No student or professor found with the given personal key.')

    def has_object_permission(self, request, view, obj):
        return obj.institute_id == request._verified_institute.id
