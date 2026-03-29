from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class InstituteScopedAccountDetailPermission(BasePermission):
    """
    Strict institute admin authentication for account-detail endpoints.

    Requires:
      - institute id in query param or request body
      - X-Admin-Key header only
    """

    message = 'You do not have permission to access this resource.'

    def _get_institute_id(self, request):
        return request.query_params.get('institute') or (
            request.data.get('institute') if hasattr(request, 'data') else None
        )

    def has_permission(self, request, view):
        from iinstitutes_list.models import Institute

        institute_id = self._get_institute_id(request)
        admin_key = request.headers.get('X-Admin-Key') or ''

        if not institute_id:
            raise PermissionDenied('Institute id is required.')

        if len(admin_key) != 32:
            raise PermissionDenied(self.message)

        try:
            institute = Institute.objects.get(pk=institute_id)
        except Institute.DoesNotExist:
            raise PermissionDenied(self.message)

        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        if institute.admin_key != admin_key:
            raise PermissionDenied(self.message)

        request._verified_institute = institute
        return True
