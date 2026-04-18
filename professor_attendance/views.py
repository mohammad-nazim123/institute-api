from django.db.models import OuterRef, Subquery

from activity_feed.services import ActivityLogMixin
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from institute_api.pagination import StandardResultsPagination
from institute_api.permissions import ADMIN_ACCESS_CONTROL, AttendancePermission
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


def get_professor_filter_value(request):
    for param_name in ('professor', 'professor_id'):
        value = (request.query_params.get(param_name) or '').strip()
        if value:
            return value
    return ''


def apply_month_or_date_filter(queryset, request):
    date_param = (request.query_params.get('date') or '').strip()
    month_param = (request.query_params.get('month') or '').strip()
    year_param = (request.query_params.get('year') or '').strip()

    if date_param:
        return queryset.filter(date=date_param)

    if month_param:
        if '-' in month_param:
            try:
                year, month = month_param.split('-')
            except ValueError as exc:
                raise ValidationError(
                    {'detail': 'Invalid month format. Please use YYYY-MM or pass month with year.'}
                ) from exc
        else:
            if not year_param:
                raise ValidationError(
                    {'detail': 'Provide year when month is passed without YYYY-MM format.'}
                )
            year, month = year_param, month_param

        try:
            year = int(year)
            month = int(month)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {'detail': 'Invalid month format. Please use YYYY-MM or pass month with year.'}
            ) from exc

        if month < 1 or month > 12:
            raise ValidationError({'detail': 'Month must be between 1 and 12.'})

        return queryset.filter(date__year=year, date__month=month)

    if year_param:
        try:
            year = int(year_param)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'detail': 'Year must be a valid number.'}) from exc
        return queryset.filter(date__year=year)

    return queryset


class ProfessorListView(APIView):
    permission_classes = [AttendancePermission]
    allowed_subordinate_access_controls = (ADMIN_ACCESS_CONTROL,)

    def get(self, request):
        institute = request._verified_institute
        queryset = (
            Professor.objects
            .filter(institute=institute)
            .select_related('experience')
            .annotate(primary_specialization=Subquery(first_specialization_subquery('pk')))
            .order_by('id')
        )
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = ProfessorDirectorySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = ProfessorDirectorySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProfessorAttendanceListCreateView(ActivityLogMixin, generics.ListCreateAPIView):
    activity_entity_type = 'professor attendance'
    activity_name_field = 'professor.name'
    permission_classes = [AttendancePermission]
    serializer_class = ProfessorAttendanceSerializer
    allowed_subordinate_access_controls = (ADMIN_ACCESS_CONTROL,)

    def get_queryset(self):
        queryset = (
            ProfessorAttendance.objects
            .select_related('professor', 'professor__experience')
            .annotate(primary_specialization=Subquery(first_specialization_subquery('professor_id')))
            .filter(institute=self.request._verified_institute)
            .order_by('-date', 'id')
        )

        professor_id = get_professor_filter_value(self.request)
        if professor_id:
            queryset = queryset.filter(professor_id=professor_id)

        return apply_month_or_date_filter(queryset, self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class ProfessorAttendanceDetailView(ActivityLogMixin, generics.RetrieveUpdateDestroyAPIView):
    activity_entity_type = 'professor attendance'
    activity_name_field = 'professor.name'
    permission_classes = [AttendancePermission]
    serializer_class = ProfessorAttendanceSerializer
    allowed_subordinate_access_controls = (ADMIN_ACCESS_CONTROL,)

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


class ProfessorLeaveListCreateView(ActivityLogMixin, generics.ListCreateAPIView):
    activity_entity_type = 'professor leave'
    activity_name_field = 'professor.name'
    permission_classes = [AttendancePermission]
    serializer_class = ProfessorLeaveSerializer
    allowed_subordinate_access_controls = (ADMIN_ACCESS_CONTROL,)

    def get_queryset(self):
        queryset = (
            ProfessorLeave.objects
            .select_related('professor', 'professor__experience')
            .filter(institute=self.request._verified_institute)
            .order_by('-date', 'id')
        )

        professor_id = get_professor_filter_value(self.request)
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


class ProfessorLeaveDetailView(ActivityLogMixin, generics.RetrieveUpdateDestroyAPIView):
    activity_entity_type = 'professor leave'
    activity_name_field = 'professor.name'
    permission_classes = [AttendancePermission]
    serializer_class = ProfessorLeaveSerializer
    allowed_subordinate_access_controls = (ADMIN_ACCESS_CONTROL,)

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
