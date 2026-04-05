from django.contrib import admin

from .models import SubordinateAccess


@admin.register(SubordinateAccess)
class SubordinateAccessAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'post',
        'name',
        'access_control',
        'access_code',
        'is_active',
    )
    list_filter = ('institute', 'is_active')
    search_fields = ('name', 'post', 'access_control', 'access_code')
