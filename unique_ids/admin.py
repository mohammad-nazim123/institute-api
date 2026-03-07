from django.contrib import admin
from .models import StuentUniqueId, ProfessorUniqueId


@admin.register(StuentUniqueId)
class StudentUniqueIdAdmin(admin.ModelAdmin):
    list_display = ('id', 'student_id', 'email', 'phone_number')
    search_fields = ('student_id', 'email', 'phone_number')


@admin.register(ProfessorUniqueId)
class ProfessorUniqueIdAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor_id', 'email', 'phone_number')
    search_fields = ('professor_id', 'email', 'phone_number')
