from django.db import models


class Course(models.Model):
    institute = models.ForeignKey('iinstitutes_list.Institute', on_delete=models.CASCADE, related_name='courses', null=True, blank=True)
    name = models.CharField(max_length=200)

    class Meta:
        indexes = [
            models.Index(fields=['institute'], name='course_institute_idx'),
        ]

    def __str__(self):
        return self.name

class Branch(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=200)

    class Meta:
        indexes = [
            models.Index(fields=['course'], name='branch_course_idx'),
        ]

    def __str__(self):
        return self.name

class AcademicTerms(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='academic_terms')
    name = models.CharField(max_length=200)

    class Meta:
        indexes = [
            models.Index(fields=['branch'], name='acterm_branch_idx'),
        ]

class Subject(models.Model):
    academic_terms=models.ForeignKey(AcademicTerms, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=200)
    unit = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['academic_terms'], name='subject_acterm_idx'),
        ]

    def __str__(self):
        return self.name
