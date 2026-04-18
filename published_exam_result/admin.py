from django.contrib import admin

from .models import PublishedExamData, PublishedObtainedMarks


@admin.register(PublishedExamData)
class PublishedExamDataAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'source_exam_data_id',
        'subject',
        'class_name',
        'branch',
        'academic_term',
        'exam_type',
    )
    search_fields = ('subject', 'class_name', 'branch', 'academic_term')
    list_filter = ('institute', 'exam_type', 'class_name', 'branch', 'academic_term')


@admin.register(PublishedObtainedMarks)
class PublishedObtainedMarksAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'published_student',
        'published_exam_data',
        'source_obtained_marks_id',
        'obtained_marks',
        'published_at',
        'updated_at',
    )
    search_fields = (
        'published_student__name',
        'published_student__student_personal_id',
        'published_exam_data__subject',
    )
    list_filter = (
        'published_exam_data__institute',
        'published_exam_data__exam_type',
        'published_exam_data__class_name',
        'published_exam_data__branch',
        'published_exam_data__academic_term',
    )
