from rest_framework.exceptions import PermissionDenied

from institute_api.permissions import FULL_ACCESS_CONTROL
from rest_framework.permissions import BasePermission


class SubordinateAccessAdminKeyPermission(BasePermission):
    message = 'Invalid or missing admin key for this institute.'

    def _get_institute_id(self, request):
        institute_id = request.query_params.get('institute')
        if not institute_id and hasattr(request, 'data'):
            institute_id = request.data.get('institute')
        return institute_id

    def has_permission(self, request, view):
        from iinstitutes_list.models import Institute

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('Institute id is required.')

        admin_key = request.headers.get('X-Admin-Key') or ''
        if len(admin_key) != 32:
            raise PermissionDenied('Admin key must be exactly 32 characters in X-Admin-Key header.')

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

        if institute.admin_key != admin_key:
            raise PermissionDenied(self.message)

        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        request._verified_institute = institute
        request._admin_key = admin_key
        request._verified_subordinate_access = None
        request._verified_access_control = FULL_ACCESS_CONTROL
        request._verified_actor_role = 'Super Admin'
        request._verified_actor_name = getattr(institute, 'super_admin_name', '')
        return True
