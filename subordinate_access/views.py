from django.utils import timezone

from activity_feed.services import ActivityLogMixin, log_activity
from rest_framework import generics
from rest_framework.viewsets import ModelViewSet

from institute_api.permissions import SuperAdminKeyPermission
from .models import SubordinateAccess
from .models import SubordinateAccessVerificationRequest
from .permissions import SubordinateAccessAdminKeyPermission
from .serializers import (
    SubordinateAccessSerializer,
    SubordinateAccessVerificationRequestSerializer,
)


class SubordinateAccessViewSet(ActivityLogMixin, ModelViewSet):
    activity_entity_type = 'subordinate access'
    activity_name_field = 'name'
    serializer_class = SubordinateAccessSerializer
    permission_classes = [SubordinateAccessAdminKeyPermission]

    def get_queryset(self):
        institute = getattr(self.request, '_verified_institute', None)
        queryset = SubordinateAccess.objects.order_by('id')
        if institute is not None:
            queryset = queryset.filter(institute=institute)
        return queryset


class SubordinateAccessVerificationRequestListView(generics.ListAPIView):
    permission_classes = [SuperAdminKeyPermission]
    serializer_class = SubordinateAccessVerificationRequestSerializer

    def get_queryset(self):
        queryset = SubordinateAccessVerificationRequest.objects.select_related(
            'institute',
            'subordinate_access',
        )
        status_filter = (self.request.query_params.get('status') or '').strip().lower()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class SubordinateAccessVerificationRequestDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [SuperAdminKeyPermission]
    serializer_class = SubordinateAccessVerificationRequestSerializer

    def get_queryset(self):
        return SubordinateAccessVerificationRequest.objects.select_related(
            'institute',
            'subordinate_access',
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        updated = serializer.save(reviewed_at=timezone.now())

        subordinate = updated.subordinate_access
        subordinate.is_active = updated.status == SubordinateAccessVerificationRequest.STATUS_APPROVED
        subordinate.save(update_fields=['is_active'])
        log_activity(
            self.request,
            institute=updated.institute,
            action='activate' if subordinate.is_active else 'deactivate',
            entity_type='subordinate access',
            entity_id=subordinate.id,
            entity_name=subordinate.name,
            description=f"{subordinate.name} access is now {'active' if subordinate.is_active else 'deactive'}.",
            details={'post': subordinate.post, 'access_control': subordinate.access_control, 'status': updated.status},
        )
