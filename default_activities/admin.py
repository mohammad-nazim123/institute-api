from django.contrib import admin

from .models import DefaultActivity


@admin.register(DefaultActivity)
class DefaultActivityAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'session_month',
        'session_year',
        'opening_time',
        'closing_time',
        'total_yearly_leaves',
    )
    search_fields = ('institute__institute_name', 'session_month', 'session_year')
