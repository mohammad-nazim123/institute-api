from django.contrib import admin
from .models import Attendance, AttendanceSubmission


@admin.register(AttendanceSubmission)
class AttendanceSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'class_name',
        'branch',
        'year_semester',
        'marked_by',
        'attendance_time',
        'submitted_at',
    )
    list_filter = ('date', 'class_name', 'branch', 'year_semester')
    search_fields = ('class_name', 'branch', 'year_semester', 'marked_by__name')
    date_hierarchy = 'date'
    ordering = ('-date', 'class_name', 'branch')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status', 'marked_by')
    list_filter = ('submission__date', 'status')
    search_fields = ('student__name',)
    date_hierarchy = 'submission__date'
    ordering = ('-submission__date',)
