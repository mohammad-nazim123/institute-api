from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class PublishedProfessorAdminKeyPermission(BasePermission):
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

        if institute.admin_key != admin_key:
            raise PermissionDenied('Invalid admin key for this institute.')

        request._verified_institute = institute
        request._admin_key = admin_key
        return True


class PublishedProfessorPersonalKeyPermission(BasePermission):
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

        request._verified_institute = institute
        request._personal_key = personal_key
        return True

    def has_object_permission(self, request, view, obj):
        return (
            obj.institute_id == request._verified_institute.id
            and obj.professor_personal_id == getattr(request, '_personal_key', None)
        )
