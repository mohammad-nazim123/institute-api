from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    get_verified_institute,
    verify_admin_key_for_institute,
)


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
        institute = get_verified_institute(request)
        admin_key = request.headers.get('X-Admin-Key')
        if not admin_key:
            raise PermissionDenied('Admin key is required (X-Admin-Key header).')

        verify_admin_key_for_institute(
            request,
            institute,
            view=view,
            message=self.message,
            admin_key=admin_key,
            allowed_subordinate_access_controls=(ADMIN_ACCESS_CONTROL,),
        )
        return True
