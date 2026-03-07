from django.db import models

class StuentUniqueId(models.Model):
    student_id = models.CharField(max_length=30, unique=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=10, unique=True)


class ProfessorUniqueId(models.Model):
    professor_id = models.CharField(max_length=30, unique=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=10, unique=True)

# Create your models here.
