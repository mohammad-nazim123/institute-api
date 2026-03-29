from django.db import models
from students.models import Student
from professors.models import Professor

class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    class_name = models.CharField(max_length=50,default="")
    branch = models.CharField(max_length=30,default="")
    year_semester = models.CharField(max_length=20,default="")
    status = models.BooleanField(default=False)  # True = Present, False = Absent
    marked_by = models.ForeignKey(Professor, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ('student', 'date')  # Prevent duplicate attendance per day
        indexes = [
            models.Index(fields=['student', 'date'], name='att_student_date_idx'),
            models.Index(fields=['class_name', 'branch', 'date'], name='att_class_branch_date_idx'),
        ]

    def __str__(self):
        return f"{self.student.name} - {self.date} - {'Present' if self.status else 'Absent'}"

# Create your models here.
