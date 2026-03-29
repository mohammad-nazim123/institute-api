from django.contrib import admin

from .models import PublishedExamSchedule, PublishedWeeklySchedule


@admin.register(PublishedWeeklySchedule)
class PublishedWeeklyScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'class_name',
        'branch',
        'academic_term',
        'published_at',
        'updated_at',
    )
    search_fields = ('institute__name', 'class_name', 'branch', 'academic_term')


@admin.register(PublishedExamSchedule)
class PublishedExamScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'class_name',
        'branch',
        'academic_term',
        'published_at',
        'updated_at',
    )
    search_fields = ('institute__name', 'class_name', 'branch', 'academic_term')
