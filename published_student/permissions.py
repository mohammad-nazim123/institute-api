from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class PublishedStudentKeyPermission(BasePermission):
    message = 'Provide X-Personal-Key with exactly 15 characters.'

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

        personal_key = request.headers.get('X-Personal-Key') or request.query_params.get('personal_key')
        if not personal_key:
            raise PermissionDenied('X-Personal-Key header is required.')
        if len(personal_key) != 15:
            raise PermissionDenied(self.message)

        try:
            institute = Institute.objects.only('id', 'institute_name', 'event_status').get(pk=institute_id)
        except Institute.DoesNotExist:
            raise PermissionDenied('Institute not found.')

        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        request._verified_institute = institute
        request._personal_key = personal_key
        return True

    def has_object_permission(self, request, view, obj):
        return (
            obj.institute_id == request._verified_institute.id
            and obj.student_personal_id == getattr(request, '_personal_key', None)
        )
