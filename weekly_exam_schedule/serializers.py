from collections import OrderedDict

from rest_framework import serializers

from .models import (
    ExamScheduleData,
    ExamScheduleDate,
    WeeklyScheduleData,
    WeeklyScheduleDay,
)


class WeeklyScheduleDataSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = WeeklyScheduleData
        fields = ['id', 'start_time', 'end_time', 'subject', 'room_number', 'professor']


class WeeklyScheduleDaySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    weekly_schedule_data = WeeklyScheduleDataSerializer(many=True, required=False)

    class Meta:
        model = WeeklyScheduleDay
        fields = ['id', 'day', 'weekly_schedule_data']


class ExamScheduleDataSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = ExamScheduleData
        fields = ['id', 'start_time', 'end_time', 'subject', 'room_number', 'type']


class ExamScheduleDateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    exam_schedule_data = ExamScheduleDataSerializer(many=True, required=False)

    class Meta:
        model = ExamScheduleDate
        fields = ['id', 'date', 'exam_schedule_data']


def serialize_weekly_entries(queryset):
    weekly_schedule = []
    weekly_days = {}

    for item in queryset:
        weekly_day = item.weekly_schedule_day
        schedule_day = weekly_days.get(weekly_day.id)

        if schedule_day is None:
            schedule_day = OrderedDict([
                ('id', weekly_day.id),
                ('day', weekly_day.day),
                ('weekly_schedule_data', []),
            ])
            weekly_days[weekly_day.id] = schedule_day
            weekly_schedule.append(schedule_day)

        schedule_day['weekly_schedule_data'].append(OrderedDict([
            ('id', item.id),
            ('start_time', item.start_time.isoformat()),
            ('end_time', item.end_time.isoformat()),
            ('subject', item.subject),
            ('room_number', item.room_number),
            ('professor', item.professor),
        ]))

    return weekly_schedule


def serialize_exam_entries(queryset):
    exam_schedule = []
    exam_dates = {}

    for item in queryset:
        exam_date = item.exam_schedule_date
        schedule_date = exam_dates.get(exam_date.id)

        if schedule_date is None:
            schedule_date = OrderedDict([
                ('id', exam_date.id),
                ('date', exam_date.date.isoformat()),
                ('exam_schedule_data', []),
            ])
            exam_dates[exam_date.id] = schedule_date
            exam_schedule.append(schedule_date)

        schedule_date['exam_schedule_data'].append(OrderedDict([
            ('id', item.id),
            ('start_time', item.start_time.isoformat()),
            ('end_time', item.end_time.isoformat()),
            ('subject', item.subject),
            ('room_number', item.room_number),
            ('type', item.type),
        ]))

    return exam_schedule


def build_schedule_dictionary(
    institute,
    class_name,
    branch,
    academic_term,
    weekly_schedule,
    exam_schedule,
):
    return OrderedDict([
        ('instutes', institute.name),
        ('id', institute.id),
        ('class', class_name),
        ('branch', branch),
        ('acedemic_terms', academic_term),
        ('Weekly_schedule', weekly_schedule),
        ('exam_schedule', exam_schedule),
    ])
