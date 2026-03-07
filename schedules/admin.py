from django.contrib import admin
from .models import (
    WeeklySchedule, ExamSchedule,
    WeeklyScheduleDay, WeeklyScheduleData,
    ExamScheduleDate, ExamScheduleData
)


@admin.register(WeeklySchedule)
class WeeklyScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'day', 'subject', 'classes', 'professor', 'start_time', 'end_time', 'room_number')
    search_fields = ('subject', 'professor', 'classes')
    list_filter = ('day',)


@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'classes', 'exam_date', 'type', 'start_time', 'end_time', 'room_number')
    search_fields = ('subject', 'classes', 'type')
    list_filter = ('type',)


@admin.register(WeeklyScheduleDay)
class WeeklyScheduleDayAdmin(admin.ModelAdmin):
    list_display = ('id', 'day', 'institute')
    search_fields = ('day',)
    list_filter = ('institute',)


@admin.register(WeeklyScheduleData)
class WeeklyScheduleDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'weekly_schedule_day', 'subject', 'classes', 'professor', 'start_time', 'end_time')
    search_fields = ('subject', 'professor', 'classes')


@admin.register(ExamScheduleDate)
class ExamScheduleDateAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'institute')
    search_fields = ('date',)
    list_filter = ('institute',)


@admin.register(ExamScheduleData)
class ExamScheduleDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'exam_schedule_date', 'subject', 'classes', 'type', 'start_time', 'end_time')
    search_fields = ('subject', 'classes', 'type')
    list_filter = ('type',)
