from rest_framework import generics

from .models import DefaultActivity
from .permissions import DefaultActivityPermission
from .serializers import DefaultActivitySerializer


class DefaultActivityListCreateView(generics.ListCreateAPIView):
    permission_classes = [DefaultActivityPermission]
    serializer_class = DefaultActivitySerializer

    def get_queryset(self):
        return DefaultActivity.objects.filter(
            institute=self.request._verified_institute,
        ).order_by('id')

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
