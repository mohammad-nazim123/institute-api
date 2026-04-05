from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    get_verified_institute,
    verify_admin_key_for_institute,
)


class InstituteEmployeeAccountPermission(BasePermission):
    """
    Requires an institute id and a 32-character X-Admin-Key header.
    The key must match the selected institute.
    """

    message = 'You do not have permission to access this resource.'

    def _get_institute_id(self, request):
        return request.query_params.get('institute') or (
            request.data.get('institute') if hasattr(request, 'data') else None
        )

    def has_permission(self, request, view):
        institute = get_verified_institute(request)
        verify_admin_key_for_institute(
            request,
            institute,
            view=view,
            message=self.message,
            allowed_subordinate_access_controls=(ADMIN_ACCESS_CONTROL,),
        )
        return True
