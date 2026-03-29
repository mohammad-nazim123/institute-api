from collections import OrderedDict

from rest_framework import serializers

from .models import PublishedExamSchedule, PublishedWeeklySchedule


class PublishedWeeklyScheduleSerializer(serializers.ModelSerializer):
    weekly_schedule = serializers.ListField(source='schedule_data', required=False)

    class Meta:
        model = PublishedWeeklySchedule
        fields = ['id', 'class_name', 'branch', 'academic_term', 'weekly_schedule']


class PublishedExamScheduleSerializer(serializers.ModelSerializer):
    exam_schedule = serializers.ListField(source='schedule_data', required=False)

    class Meta:
        model = PublishedExamSchedule
        fields = ['id', 'class_name', 'branch', 'academic_term', 'exam_schedule']


def build_weekly_response(institute, hierarchy, weekly_schedule, **extra):
    payload = OrderedDict([
        ('id', institute.id),
        ('name', institute.name),
        ('class_name', hierarchy['class_name']),
        ('branch', hierarchy['branch']),
        ('academic_term', hierarchy['academic_term']),
        ('weekly_schedule', weekly_schedule),
    ])
    for key, value in extra.items():
        payload[key] = value
    return payload


def build_exam_response(institute, hierarchy, exam_schedule, **extra):
    payload = OrderedDict([
        ('id', institute.id),
        ('name', institute.name),
        ('class_name', hierarchy['class_name']),
        ('branch', hierarchy['branch']),
        ('academic_term', hierarchy['academic_term']),
        ('exam_schedule', exam_schedule),
    ])
    for key, value in extra.items():
        payload[key] = value
    return payload
