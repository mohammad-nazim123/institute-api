from django.contrib import admin
from .models import (
    Professor, ProfessorAddress, ProfessorQualification,
    ProfessorExperience, professorAdminEmployement, professorClassAssigned
)


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'gender', 'phone_number', 'institute')
    search_fields = ('name', 'email', 'phone_number')
    list_filter = ('gender', 'institute')


@admin.register(ProfessorAddress)
class ProfessorAddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor', 'city', 'state', 'country')
    search_fields = ('professor__name', 'city', 'state')


@admin.register(ProfessorQualification)
class ProfessorQualificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor', 'degree', 'institution', 'year_of_passing', 'percentage')
    search_fields = ('professor__name', 'degree', 'institution')


@admin.register(ProfessorExperience)
class ProfessorExperienceAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor', 'designation', 'department', 'teaching_experience')
    search_fields = ('professor__name', 'designation', 'department')


@admin.register(professorAdminEmployement)
class ProfessorAdminEmployementAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor', 'personal_id', 'employee_id', 'employement_type', 'salary')
    search_fields = ('professor__name', 'personal_id', 'employee_id')


@admin.register(professorClassAssigned)
class ProfessorClassAssignedAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor', 'assigned_course', 'assigned_section', 'assigned_year', 'session')
    search_fields = ('professor__name', 'assigned_course')
