from django.contrib import admin
from .models import Course, Subject


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'institute')
    search_fields = ('name',)
    list_filter = ('institute',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'course', 'unit')
    search_fields = ('name', 'course__name')
    list_filter = ('course',)
