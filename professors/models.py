from django.db import models


class Professor(models.Model):
    institute = models.ForeignKey('iinstitutes_list.Institute', on_delete=models.CASCADE, related_name='professors', null=True, blank=True)
    name = models.CharField(max_length=30,default="")
    father_name = models.CharField(max_length=30,default="")
    mother_name = models.CharField(max_length=30,default="")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10,default="")
    phone_number = models.CharField(max_length=20,default="")
    email = models.EmailField(default="")
    indentity_number = models.CharField(max_length=30,default="")
    marital_status = models.CharField(max_length=15,default="")

    class Meta:
        indexes = [
            models.Index(fields=['institute', 'email'], name='prof_inst_email_idx'),
            models.Index(fields=['institute', 'name'], name='prof_inst_name_idx'),
            models.Index(fields=['institute', 'phone_number'], name='prof_inst_phone_idx'),
        ]

class ProfessorAddress(models.Model):
    professor = models.OneToOneField(Professor, on_delete=models.CASCADE,related_name="address")
    current_address = models.CharField(max_length=100,default="")
    permanent_address = models.CharField(max_length=100,default="")
    city = models.CharField(max_length=20,default="")
    state = models.CharField(max_length=20,default="")
    country = models.CharField(max_length=20,default="")

class ProfessorQualification(models.Model):
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE,related_name="qualification")
    degree = models.CharField(max_length=20,default="")
    institution = models.CharField(max_length=30,default="")
    year_of_passing = models.CharField(max_length=10,default="")
    percentage = models.CharField(max_length=10,default="")
    specialization = models.CharField(max_length=30,default="")

class ProfessorExperience(models.Model):
    professor = models.OneToOneField(Professor, on_delete=models.CASCADE,related_name="experience")
    designation = models.CharField(max_length=30,default="")
    department = models.CharField(max_length=30,default="")
    teaching_subject = models.CharField(max_length=30,default="")
    teaching_experience = models.CharField(max_length=10,default="")
    interest = models.CharField(max_length=50,default="")

    class Meta:
        indexes = [
            models.Index(fields=['department'], name='prof_exp_dept_idx'),
        ]

class professorAdminEmployement(models.Model):
    professor = models.OneToOneField(Professor, on_delete=models.CASCADE,related_name="admin_employement")
    personal_id = models.CharField(max_length=30,default="")
    employee_id = models.CharField(max_length=30,default="")
    date_of_joining = models.DateField(null=True, blank=True)
    employement_type = models.CharField(max_length=20,default="")
    working_hours = models.CharField(max_length=10,default="")
    salary = models.CharField(max_length=20,default="")

    class Meta:
        indexes = [
            models.Index(fields=['employee_id'], name='prof_admin_empid_idx'),
            models.Index(fields=['personal_id'], name='prof_admin_pid_idx'),
        ]

class professorClassAssigned(models.Model):
    professor = models.OneToOneField(Professor, on_delete=models.CASCADE,related_name="class_assigned")
    assigned_course = models.CharField(max_length=30,default="")
    assigned_section = models.CharField(max_length=20,default="")
    assigned_year = models.CharField(max_length=20,default="")
    session = models.CharField(max_length=15,default="")
    
        
    
    
    
    

# Create your models here.
