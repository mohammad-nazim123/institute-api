from rest_framework import generics

from institute_api.pagination import StandardResultsPagination

from .models import AcademicTerm, DefaultActivity
from .permissions import DefaultActivityPermission
from .serializers import AcademicTermSerializer, DefaultActivitySerializer


class DefaultActivityListCreateView(generics.ListCreateAPIView):
    permission_classes = [DefaultActivityPermission]
    serializer_class = DefaultActivitySerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return DefaultActivity.objects.filter(
            institute=self.request._verified_institute,
        ).select_related('institute').order_by('id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class DefaultActivityDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [DefaultActivityPermission]
    serializer_class = DefaultActivitySerializer

    def get_queryset(self):
        return DefaultActivity.objects.filter(
            institute=self.request._verified_institute,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class AcademicTermListCreateView(generics.ListCreateAPIView):
    permission_classes = [DefaultActivityPermission]
    serializer_class = AcademicTermSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return AcademicTerm.objects.filter(
            institute=self.request._verified_institute,
        ).select_related('institute').order_by('sort_order', 'id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class AcademicTermDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [DefaultActivityPermission]
    serializer_class = AcademicTermSerializer

    def get_queryset(self):
        return AcademicTerm.objects.filter(
            institute=self.request._verified_institute,
        ).order_by('sort_order', 'id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context
