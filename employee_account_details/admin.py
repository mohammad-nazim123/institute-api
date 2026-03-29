from django.contrib import admin

from .models import EmployeeAccountDetail


@admin.register(EmployeeAccountDetail)
class EmployeeAccountDetailAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'professor',
        'account_holder_name',
        'bank_name',
        'account_number',
        'ifsc_code',
    )
    search_fields = (
        'institute__name',
        'professor__name',
        'account_holder_name',
        'bank_name',
        'account_number',
        'ifsc_code',
    )
    list_filter = ('institute', 'bank_name')
