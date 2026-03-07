from django.db import models


class Course(models.Model):
    institute = models.ForeignKey('iinstitutes_list.Institute', on_delete=models.CASCADE, related_name='courses', null=True, blank=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

class Subject(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=200)
    unit = models.IntegerField(default=0)

    def __str__(self):
        return self.name


# Create your models here.
