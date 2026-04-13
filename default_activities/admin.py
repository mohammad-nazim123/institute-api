from django.contrib import admin

from .models import AcademicTerm, DefaultActivity


@admin.register(DefaultActivity)
class DefaultActivityAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'session_month',
        'session_year',
        'academic_terms_type',
        'opening_time',
        'closing_time',
        'total_yearly_leaves',
    )
    search_fields = ('institute__institute_name', 'session_month', 'session_year')


@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'institute', 'sort_order')
    list_filter = ('institute',)
    search_fields = ('name', 'institute__institute_name')
