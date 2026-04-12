from django.contrib import admin
from .models import (
    Student, StudentContactDetails, StudentEducationDetails,
    StudentAdmissionDetails, StudentCourseAssignment,
    StudentFeeDetails, StudentSystemDetails
)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'gender', 'category', 'institute')
    search_fields = ('name', 'identity')
    list_filter = ('gender', 'category', 'institute')


@admin.register(StudentContactDetails)
class StudentContactDetailsAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'email', 'mobile', 'father_name', 'mother_name', 'guardian_name')
    search_fields = ('student__name', 'email', 'mobile')


@admin.register(StudentEducationDetails)
class StudentEducationDetailsAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'qualification', 'passing_year', 'instutute_name', 'marks_obtained')
    search_fields = ('student__name', 'qualification', 'instutute_name')


@admin.register(StudentAdmissionDetails)
class StudentAdmissionDetailsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'student',
        'enrollment_number',
        'roll_number',
        'admission_date',
        'start_class_date',
        'academic_year',
    )
    search_fields = ('student__name', 'enrollment_number', 'roll_number')


@admin.register(StudentCourseAssignment)
class StudentCourseAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'class_name', 'branch', 'academic_term')
    search_fields = ('student__name', 'class_name', 'branch', 'academic_term')


@admin.register(StudentFeeDetails)
class StudentFeeDetailsAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'total_fee_amount', 'paid_amount', 'pending_amount')
    search_fields = ('student__name',)


@admin.register(StudentSystemDetails)
class StudentSystemDetailsAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'student_personal_id', 'library_card_number', 'varification_status')
    search_fields = ('student__name', 'student_personal_id', 'library_card_number')
    list_filter = ('varification_status',)
