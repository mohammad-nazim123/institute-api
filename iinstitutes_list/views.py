from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from collections import OrderedDict
from .models import Institute
from .serializers import InstituteSerializer, InstituteDetailSerializer, InstituteVerifySerializer


class InstituteViewSet(ModelViewSet):
    serializer_class = InstituteSerializer

    def get_queryset(self):
        return Institute.objects.prefetch_related(
            'students__contact_details',
            'students__education_details',
            'students__course_details',
            'students__admission_details',
            'students__course_assignments',
            'students__fee_details',
            'students__system_details',
            'professors__address',
            'professors__qualification',
            'professors__experience',
            'professors__admin_employement',
            'professors__class_assigned',
            'courses__subjects',
            'weekly_schedule_days__weekly_schedule_data',
            'exam_schedule_dates__exam_schedule_data',
        ).all()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return InstituteDetailSerializer
        return InstituteSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        # Wrap the single instance in a list as requested
        return Response([serializer.data])


class InstituteVerifyView(APIView):
    """
    POST /institutes/verify/
    Accepts {"name": "...", "admin_key": "..."}
    Returns the institute data if the pair matches, or 403 if not.
    """

    def post(self, request):
        serializer = InstituteVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']
        admin_key = serializer.validated_data['admin_key']

        try:
            institute = Institute.objects.get(name=name, admin_key=admin_key)
        except Institute.DoesNotExist:
            return Response(
                {'detail': 'Invalid institute name or admin key.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Return the institute data using the detail serializer
        detail_serializer = InstituteDetailSerializer(institute)
        return Response(detail_serializer.data)
