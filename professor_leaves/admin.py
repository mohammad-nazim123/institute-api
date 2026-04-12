from django.contrib import admin

from .models import InstituteTotalLeave, ProfessorLeave


@admin.register(ProfessorLeave)
class ProfessorLeaveAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'professor_name',
        'department',
        'email',
        'start_date',
        'end_date',
        'total_days',
        'institute',
    )
    search_fields = ('professor_name', 'department', 'email')
    list_filter = ('institute', 'start_date', 'end_date')


@admin.register(InstituteTotalLeave)
class InstituteTotalLeaveAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'session_start_month',
        'session_end_month',
        'opening_time',
        'closing_time',
        'total_leaves',
    )
    search_fields = ('institute__name',)
