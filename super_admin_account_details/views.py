from django.db import transaction
from rest_framework import generics

from activity_feed.services import ActivityLogMixin

from .models import SuperAdminAccountDetail
from .permissions import InstituteScopedAccountDetailPermission
from .serializers import SuperAdminAccountDetailSerializer


class SuperAdminAccountDetailListCreateView(ActivityLogMixin, generics.ListCreateAPIView):
    activity_entity_type = 'super admin account detail'
    activity_name_field = 'account_holder_name'
    permission_classes = [InstituteScopedAccountDetailPermission]
    serializer_class = SuperAdminAccountDetailSerializer

    def get_queryset(self):
        queryset = SuperAdminAccountDetail.objects.filter(
            institute=self.request._verified_institute
        ).order_by('-is_default', 'id')

        default_only = str(self.request.query_params.get('default_only', '')).strip().lower()
        if default_only in {'1', 'true', 'yes'}:
            queryset = queryset.filter(is_default=True)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class SuperAdminAccountDetailDetailView(ActivityLogMixin, generics.RetrieveUpdateDestroyAPIView):
    activity_entity_type = 'super admin account detail'
    activity_name_field = 'account_holder_name'
    permission_classes = [InstituteScopedAccountDetailPermission]
    serializer_class = SuperAdminAccountDetailSerializer

    def get_queryset(self):
        return SuperAdminAccountDetail.objects.filter(
            institute=self.request._verified_institute
        )

    def perform_destroy(self, instance):
        institute = instance.institute
        was_default = instance.is_default

        with transaction.atomic():
            super().perform_destroy(instance)

            if was_default:
                next_default = SuperAdminAccountDetail.objects.filter(
                    institute=institute
                ).order_by('id').first()

                if next_default and not next_default.is_default:
                    next_default.is_default = True
                    next_default.save(update_fields=['is_default', 'updated_at'])
