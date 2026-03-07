from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from collections import OrderedDict
from .models import WeeklySchedule, ExamSchedule, WeeklyScheduleDay, ExamScheduleDate
from .serializers import (
    WeeklyScheduleSerializer, ExamScheduleSerializer,
    WeeklyScheduleDaySerializer, ExamScheduleDateSerializer
)
from institute_api.mixins import InstituteDictResponseMixin
from institute_api.permissions import SchedulePermission


class WeeklyScheduleViewSet(ModelViewSet):
    queryset = WeeklySchedule.objects.all()
    serializer_class = WeeklyScheduleSerializer
    permission_classes = [SchedulePermission]


class ExamScheduleViewSet(ModelViewSet):
    queryset = ExamSchedule.objects.all()
    serializer_class = ExamScheduleSerializer
    permission_classes = [SchedulePermission]


class WeeklyScheduleDayViewSet(InstituteDictResponseMixin, ModelViewSet):
    serializer_class = WeeklyScheduleDaySerializer
    entity_key = 'weekly_schedules'
    entity_name_field = 'day'
    permission_classes = [SchedulePermission]

    def get_queryset(self):
        return WeeklyScheduleDay.objects.select_related(
            'institute',
        ).prefetch_related(
            'weekly_schedule_data',
        ).all()


class ExamScheduleDateViewSet(InstituteDictResponseMixin, ModelViewSet):
    serializer_class = ExamScheduleDateSerializer
    entity_key = 'exam_schedules'
    entity_name_field = 'date'
    permission_classes = [SchedulePermission]

    def get_queryset(self):
        return ExamScheduleDate.objects.select_related(
            'institute',
        ).prefetch_related(
            'exam_schedule_data',
        ).all()
