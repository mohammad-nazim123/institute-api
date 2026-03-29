from rest_framework import generics

from .models import EmployeeAccountDetail
from .permissions import InstituteEmployeeAccountPermission
from .serializers import EmployeeAccountDetailSerializer


class EmployeeAccountDetailListCreateView(generics.ListCreateAPIView):
    permission_classes = [InstituteEmployeeAccountPermission]
    serializer_class = EmployeeAccountDetailSerializer

    def get_queryset(self):
        queryset = EmployeeAccountDetail.objects.select_related('professor').filter(
            institute=self.request._verified_institute
        ).order_by('id')

        professor_id = self.request.query_params.get('professor')
        if professor_id:
            queryset = queryset.filter(professor_id=professor_id)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class EmployeeAccountDetailDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [InstituteEmployeeAccountPermission]
    serializer_class = EmployeeAccountDetailSerializer

    def get_queryset(self):
        return EmployeeAccountDetail.objects.select_related('professor').filter(
            institute=self.request._verified_institute
        )
