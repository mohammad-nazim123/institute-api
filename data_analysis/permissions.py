from rest_framework.permissions import BasePermission

from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    get_verified_institute,
    verify_admin_key_for_institute,
)


class DataAnalysisAdminPermission(BasePermission):
    message = 'You do not have permission to access this resource.'

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
