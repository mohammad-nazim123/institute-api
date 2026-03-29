import json

from django.contrib import admin
from django.utils.html import format_html

from .models import PublishedStudent


@admin.register(PublishedStudent)
class PublishedStudentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'institute',
        'source_student_id',
        'student_personal_id',
        'subject_count',
        'updated_at',
    )
    search_fields = ('name', 'source_student_id', 'student_personal_id', 'institute__name')
    list_filter = ('institute', 'published_at', 'updated_at')
    list_select_related = ('institute',)
    ordering = ('institute__name', 'source_student_id')
    readonly_fields = (
        'published_at',
        'updated_at',
        'student_data_pretty',
        'subjects_assigned_pretty',
    )
    fieldsets = (
        (
            'Published Student',
            {
                'fields': (
                    'institute',
                    'source_student_id',
                    'name',
                    'student_personal_id',
                    'published_at',
                    'updated_at',
                )
            },
        ),
        (
            'Student Snapshot',
            {
                'fields': ('student_data_pretty',),
            },
        ),
        (
            'Assigned Subjects',
            {
                'fields': ('subjects_assigned_pretty',),
            },
        ),
    )

    @admin.display(description='Subjects')
    def subject_count(self, obj):
        return len(obj.subjects_assigned or [])

    @admin.display(description='Student Data')
    def student_data_pretty(self, obj):
        return format_html(
            '<pre style="white-space: pre-wrap; max-width: 100%; margin: 0;">{}</pre>',
            json.dumps(obj.student_data or {}, indent=2, ensure_ascii=True),
        )

    @admin.display(description='Assigned Subjects')
    def subjects_assigned_pretty(self, obj):
        return format_html(
            '<pre style="white-space: pre-wrap; max-width: 100%; margin: 0;">{}</pre>',
            json.dumps(obj.subjects_assigned or [], indent=2, ensure_ascii=True),
        )
