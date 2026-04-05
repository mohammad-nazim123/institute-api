from django.contrib import admin

from .models import ActivityEvent


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'actor_role',
        'actor_name',
        'action',
        'entity_type',
        'occurred_at',
    )
    list_filter = ('entity_type', 'action', 'actor_role', 'actor_access_control')
    search_fields = ('title', 'description', 'entity_name', 'actor_name', 'actor_role')
