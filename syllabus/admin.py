from django.contrib import admin
from .models import Course, Branch, Subject


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'institute')
    search_fields = ('name',)
    list_filter = ('institute',)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'course')
    search_fields = ('name', 'course__name')
    list_filter = ('course',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'academic_terms', 'unit')
    search_fields = ('name', 'academic_terms__name')
    list_filter = ('academic_terms',)
