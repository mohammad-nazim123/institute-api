from django.contrib import admin

from .models import SuperAdminAccountDetail


@admin.register(SuperAdminAccountDetail)
class SuperAdminAccountDetailAdmin(admin.ModelAdmin):
    list_display = ('id', 'institute', 'account_holder_name', 'bank_name', 'account_number', 'ifsc_code')
    search_fields = ('institute__institute_name', 'account_holder_name', 'bank_name', 'account_number', 'ifsc_code')
    list_filter = ('institute',)
