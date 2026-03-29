import hmac

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class PublishedScheduleAdminKeyPermission(BasePermission):
    message = 'Provide X-Admin-Key with exactly 32 characters.'

    def _get_institute_id(self, request):
        return (
            request.query_params.get('institute')
            or (request.data.get('institute') if hasattr(request, 'data') else None)
        )

    def has_permission(self, request, view):
        from iinstitutes_list.models import Institute

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (?institute= query param or body field).')

        admin_key = request.headers.get('X-Admin-Key')
        if not admin_key:
            raise PermissionDenied('X-Admin-Key header is required.')
        if len(admin_key) != 32:
            raise PermissionDenied(self.message)

        try:
            institute = Institute.objects.only('id', 'name', 'admin_key', 'event_status').get(pk=institute_id)
        except Institute.DoesNotExist:
            raise PermissionDenied('Institute not found.')

        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        if not hmac.compare_digest(admin_key, institute.admin_key):
            raise PermissionDenied('Invalid admin key for this institute.')

        request._verified_institute = institute
        request._admin_key = admin_key
        return True


class PublishedSchedulePersonalKeyPermission(BasePermission):
    message = 'Provide X-Personal-Key with exactly 15 characters.'

    def _get_institute_id(self, request):
        return (
            request.query_params.get('institute')
            or (request.data.get('institute') if hasattr(request, 'data') else None)
        )

    def has_permission(self, request, view):
        from iinstitutes_list.models import Institute
        from professors.models import professorAdminEmployement
        from students.models import StudentSystemDetails

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (?institute= query param or body field).')

        personal_key = request.headers.get('X-Personal-Key')
        if not personal_key:
            raise PermissionDenied('X-Personal-Key header is required.')
        if len(personal_key) != 15:
            raise PermissionDenied(self.message)

        try:
            institute = Institute.objects.only('id', 'name', 'event_status').get(pk=institute_id)
        except Institute.DoesNotExist:
            raise PermissionDenied('Institute not found.')

        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        try:
            professor_employment = professorAdminEmployement.objects.select_related(
                'professor__institute'
            ).get(personal_id=personal_key)
            if professor_employment.professor.institute_id != institute.id:
                raise PermissionDenied('Professor personal key does not belong to this institute.')

            request._verified_institute = institute
            request._verified_professor = professor_employment.professor
            request._personal_key = personal_key
            return True
        except professorAdminEmployement.DoesNotExist:
            pass

        try:
            system_details = StudentSystemDetails.objects.select_related(
                'student__institute',
                'student__course_assignments',
            ).get(student_personal_id=personal_key)
        except StudentSystemDetails.DoesNotExist:
            raise PermissionDenied('No professor or student found with the given personal key.')

        if system_details.student.institute_id != institute.id:
            raise PermissionDenied('Student personal key does not belong to this institute.')

        request._verified_institute = institute
        request._verified_student = system_details.student
        request._personal_key = personal_key
        return True


class PublishedScheduleAccessPermission(BasePermission):
    message = 'Provide X-Admin-Key or X-Personal-Key in the request headers.'

    def has_permission(self, request, view):
        admin_key = request.headers.get('X-Admin-Key')
        personal_key = request.headers.get('X-Personal-Key')

        if admin_key:
            return PublishedScheduleAdminKeyPermission().has_permission(request, view)
        if personal_key:
            return PublishedSchedulePersonalKeyPermission().has_permission(request, view)

        raise PermissionDenied(self.message)
