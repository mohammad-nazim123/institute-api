from django.contrib import admin
from .models import ProfessorAttendance, ProfessorLeave


@admin.register(ProfessorAttendance)
class ProfessorAttendanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor', 'date', 'status', 'attendance_time')
    search_fields = ('professor__name', 'professor__email')
    list_filter = ('date', 'status', 'institute')


@admin.register(ProfessorLeave)
class ProfessorLeaveAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor', 'date', 'status')
    search_fields = ('professor__name', 'professor__email', 'comment')
    list_filter = ('date', 'status', 'institute')
