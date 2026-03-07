from django.db import models
from django.utils import timezone

class Student(models.Model):
    institute = models.ForeignKey('iinstitutes_list.Institute', on_delete=models.CASCADE, related_name='students', null=True, blank=True)
    name = models.CharField(max_length=100,default="")
    age = models.IntegerField(default=0)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10,default="")
    nationality = models.CharField(max_length=50,default="")
    identity = models.CharField(max_length=50,default="")
    category = models.CharField(max_length=20,default="")

    def __str__(self):
        return self.name

class StudentContactDetails(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='contact_details')
    email = models.EmailField(unique=True,default="")
    parmannent_address = models.TextField(default="")
    current_address = models.TextField(default="")
    mobile = models.CharField(max_length=15,default="")
    father_name = models.CharField(max_length=100,default="")
    mother_name = models.CharField(max_length=100,default="")
    parent_contact = models.CharField(max_length=15,default="")

    def __str__(self):
        return self.email

class StudentEducationDetails(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='education_details')
    qualification = models.CharField(max_length=100,default="")
    passing_year = models.IntegerField(default=0)
    instutute_name = models.CharField(max_length=100,default="")
    marks_obtained = models.CharField(max_length=10,default="")

    def __str__(self):
        return self.qualification

class StudentCourseDetails(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='course_details')
    course_name = models.CharField(max_length=100,default="")
    branch = models.CharField(max_length=100,default="")
    session_mode = models.CharField(max_length=50,default="")

# class StudentOtherDetails(models.Model):
#     student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='identity_details')
#     category = models.CharField(max_length=50,default="")
#     blood_group = models.CharField(max_length=10,default="")
#     emergency_contact = models.CharField(max_length=15,default="")

class StudentAdmissionDetails(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='admission_details')
    enrollment_number = models.CharField(max_length=50,default="")
    roll_number = models.CharField(max_length=50,default="")
    admission_date = models.DateField(null=True, blank=True)
    academic_year = models.CharField(max_length=20,default="")
    # student_status = models.CharField(max_length=20,default="")

class StudentCourseAssignment(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='course_assignments')
    course_name = models.CharField(max_length=100,default="")
    year = models.CharField(max_length=20,default="")
    batch = models.CharField(max_length=20,default="")

class StudentFeeDetails(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='fee_details')
    total_fee_amount = models.FloatField(default=0.0)
    paid_amount = models.FloatField(default=0.0)
    pending_amount = models.FloatField(default=0.0)
    # other_amount = models.FloatField(default=0.0)

# class StudentDocument(models.Model):
#     student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='documents')
#     photograph = models.ImageField(upload_to='student_photos/', null=True, blank=True)
#     identity_proof = models.FileField(upload_to='student_identity_proofs/', null=True, blank=True)
#     signature = models.ImageField(upload_to='student_signatures/', null=True, blank=True)
#     visa_proof = models.FileField(upload_to='student_visa_proofs/', null=True, blank=True)

class StudentSystemDetails(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='system_details')
    student_personal_id = models.CharField(max_length=50,default="")
    library_card_number = models.CharField(max_length=50,default="")
    hostel_details = models.CharField(max_length=100,default="")
    varification_status = models.CharField(max_length=20,default="")

class AttedanceDate(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_dates')
    date = models.DateField(default=timezone.now)
    


class SubjectsAssigned(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='subjects_assigned')
    subject = models.CharField(max_length=30,default="")
    unit = models.CharField(max_length=10,default="")
    