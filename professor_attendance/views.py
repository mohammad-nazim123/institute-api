from django.db.models import OuterRef, Subquery
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from institute_api.permissions import AttendancePermission
from professors.models import Professor, ProfessorQualification

from .models import ProfessorAttendance, ProfessorLeave
from .serializers import (
    ProfessorAttendanceSerializer,
    ProfessorDirectorySerializer,
    ProfessorLeaveSerializer,
)


def first_specialization_subquery(professor_field):
    return ProfessorQualification.objects.filter(
        professor_id=OuterRef(professor_field)
    ).order_by('id').values('specialization')[:1]


def apply_month_or_date_filter(queryset, request):
    date_param = request.query_params.get('date')
    month_param = request.query_params.get('month')

    if date_param:
        return queryset.filter(date=date_param)

    if month_param:
        try:
            year, month = month_param.split('-')
        except ValueError as exc:
            raise ValidationError({'detail': 'Invalid month format. Please use YYYY-MM.'}) from exc
        return queryset.filter(date__year=year, date__month=month)

    return queryset


class ProfessorListView(APIView):
    permission_classes = [AttendancePermission]

    def get(self, request):
        institute = request._verified_institute
        queryset = (
            Professor.objects
            .filter(institute=institute)
            .select_related('experience')
            .annotate(primary_specialization=Subquery(first_specialization_subquery('pk')))
            .order_by('id')
        )
        serializer = ProfessorDirectorySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProfessorAttendanceListCreateView(generics.ListCreateAPIView):
    permission_classes = [AttendancePermission]
    serializer_class = ProfessorAttendanceSerializer

    def get_queryset(self):
        queryset = (
            ProfessorAttendance.objects
            .select_related('professor', 'professor__experience')
            .annotate(primary_specialization=Subquery(first_specialization_subquery('professor_id')))
            .filter(institute=self.request._verified_institute)
            .order_by('-date', 'id')
        )

        professor_id = self.request.query_params.get('professor')
        if professor_id:
            queryset = queryset.filter(professor_id=professor_id)

        return apply_month_or_date_filter(queryset, self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class ProfessorAttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [AttendancePermission]
    serializer_class = ProfessorAttendanceSerializer

    def get_queryset(self):
        return (
            ProfessorAttendance.objects
            .select_related('professor', 'professor__experience')
            .annotate(primary_specialization=Subquery(first_specialization_subquery('professor_id')))
            .filter(institute=self.request._verified_institute)
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class ProfessorLeaveListCreateView(generics.ListCreateAPIView):
    permission_classes = [AttendancePermission]
    serializer_class = ProfessorLeaveSerializer

    def get_queryset(self):
        queryset = (
            ProfessorLeave.objects
            .select_related('professor', 'professor__experience')
            .filter(institute=self.request._verified_institute)
            .order_by('-date', 'id')
        )

        professor_id = self.request.query_params.get('professor')
        if professor_id:
            queryset = queryset.filter(professor_id=professor_id)

        status_param = (self.request.query_params.get('status') or '').strip()
        if status_param:
            if status_param == 'rejected':
                status_param = ProfessorLeave.STATUS_REJECT
            queryset = queryset.filter(status=status_param)

        return apply_month_or_date_filter(queryset, self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class ProfessorLeaveDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [AttendancePermission]
    serializer_class = ProfessorLeaveSerializer

    def get_queryset(self):
        return (
            ProfessorLeave.objects
            .select_related('professor', 'professor__experience')
            .filter(institute=self.request._verified_institute)
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context
