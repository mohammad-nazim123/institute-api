from rest_framework import generics

from .models import SuperAdminAccountDetail
from .permissions import InstituteScopedAccountDetailPermission
from .serializers import SuperAdminAccountDetailSerializer


class SuperAdminAccountDetailListCreateView(generics.ListCreateAPIView):
    permission_classes = [InstituteScopedAccountDetailPermission]
    serializer_class = SuperAdminAccountDetailSerializer

    def get_queryset(self):
        return SuperAdminAccountDetail.objects.filter(
            institute=self.request._verified_institute
        ).order_by('id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class SuperAdminAccountDetailDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [InstituteScopedAccountDetailPermission]
    serializer_class = SuperAdminAccountDetailSerializer

    def get_queryset(self):
        return SuperAdminAccountDetail.objects.filter(
            institute=self.request._verified_institute
        )
