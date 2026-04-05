from django.contrib import admin

from .models import ArchiveRecord


@admin.register(ArchiveRecord)
class ArchiveRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'institute', 'entity_type', 'source_id', 'name', 'archived_at')
    list_filter = ('entity_type', 'institute')
    search_fields = ('name', 'source_id')
