from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    STUDENT_ACCESS_CONTROL,
    get_verified_institute,
    verify_admin_key_for_institute,
)


class PublishedExamResultAccessPermission(BasePermission):
    message = 'Provide X-Admin-Key or X-Personal-Key (student personal ID).'

    def has_permission(self, request, view):
        from students.models import StudentSystemDetails

        admin_key = request.headers.get('X-Admin-Key') or request.query_params.get('admin_key') or ''
        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key') or ''

        if not admin_key and not personal_key:
            raise PermissionDenied(self.message)

        institute = get_verified_institute(request)

        if admin_key:
            if len(admin_key) not in {30, 31, 32}:
                raise PermissionDenied(
                    'Provide X-Admin-Key or admin_key with exactly 30, 31, or 32 characters.'
                )

            verify_admin_key_for_institute(
                request,
                institute,
                view=view,
                message='Invalid admin key for this institute.',
                admin_key=admin_key,
                allowed_subordinate_access_controls=(
                    ADMIN_ACCESS_CONTROL,
                    STUDENT_ACCESS_CONTROL,
                ),
            )
            return True

        if len(personal_key) != 15:
            raise PermissionDenied('Provide X-Personal-Key with exactly 15 characters.')

        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            raise PermissionDenied(
                'Students can only read published exam results. Write operations require X-Admin-Key.'
            )

        try:
            system_details = StudentSystemDetails.objects.select_related(
                'student__institute'
            ).get(student_personal_id=personal_key)
        except StudentSystemDetails.DoesNotExist:
            raise PermissionDenied('No student found with the given personal key.')

        if system_details.student.institute_id != institute.id:
            raise PermissionDenied('Student personal key does not belong to this institute.')

        request._verified_institute = institute
        request._verified_student = system_details.student
        request._personal_key = personal_key
        return True
