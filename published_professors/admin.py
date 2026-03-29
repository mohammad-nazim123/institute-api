from django.contrib import admin

from .models import PublishedProfessor


@admin.register(PublishedProfessor)
class PublishedProfessorAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'source_professor_id',
        'name',
        'email',
        'professor_personal_id',
        'published_at',
        'updated_at',
    )
    search_fields = ('name', 'email', 'source_professor_id', 'professor_personal_id', 'institute__name')
    list_filter = ('institute', 'published_at', 'updated_at')
    readonly_fields = ('published_at', 'updated_at')
