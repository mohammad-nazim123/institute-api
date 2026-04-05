from django.contrib import admin

from .models import PublishedExamResult


@admin.register(PublishedExamResult)
class PublishedExamResultAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'source_student_id',
        'name',
        'student_personal_id',
        'published_at',
        'updated_at',
    )
    search_fields = (
        'name',
        'student_personal_id',
    )
    list_filter = ('institute',)
