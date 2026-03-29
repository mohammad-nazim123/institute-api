from django.contrib import admin
from .models import ExamData, ObtainedMarks


@admin.register(ExamData)
class ExamDataAdmin(admin.ModelAdmin):
    list_display = ['id', 'institute', 'class_name', 'branch', 'academic_term', 'subject', 'exam_type', 'date', 'total_marks']
    list_filter = ['exam_type', 'class_name', 'branch', 'academic_term']
    search_fields = ['subject', 'exam_type', 'class_name', 'branch']


@admin.register(ObtainedMarks)
class ObtainedMarksAdmin(admin.ModelAdmin):
    list_display = ['id', 'exam_data', 'student', 'obtained_marks']
    search_fields = ['student__name', 'exam_data__subject']
