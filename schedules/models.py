from django.db import models


class WeeklySchedule(models.Model):
    start_time = models.TimeField(default="")
    end_time = models.TimeField(default="")
    day = models.CharField(max_length=15,default="")
    subject = models.CharField(max_length=30,default="")
    classes = models.CharField(max_length=20,default="") 
    room_number = models.CharField(max_length=10,default="") 
    professor = models.CharField(max_length=30,default="")

    def __str__(self):
        return self.subject

class ExamSchedule(models.Model):
    start_time = models.TimeField(default="")
    end_time = models.TimeField(default="")
    subject = models.CharField(max_length=30,default="")
    classes = models.CharField(max_length=20,default="") 
    room_number = models.CharField(max_length=10,default="") 
    exam_date = models.DateField(default="")
    type = models.CharField(max_length=15,default="")

    def __str__(self):
        return self.subject

class WeeklyScheduleDay(models.Model):
    institute = models.ForeignKey('iinstitutes_list.Institute', on_delete=models.CASCADE, related_name='weekly_schedule_days', null=True, blank=True)
    day = models.CharField(max_length=15,default="")
    
class WeeklyScheduleData(models.Model):
    weekly_schedule_day = models.ForeignKey(WeeklyScheduleDay, on_delete=models.CASCADE,related_name="weekly_schedule_data")
    start_time = models.TimeField(default="")
    end_time = models.TimeField(default="")
    subject = models.CharField(max_length=30,default="")
    classes = models.CharField(max_length=20,default="") 
    room_number = models.CharField(max_length=10,default="") 
    professor = models.CharField(max_length=30,default="")

    def __str__(self):
        return self.subject

        return self.subject

class ExamScheduleDate(models.Model):
    institute = models.ForeignKey('iinstitutes_list.Institute', on_delete=models.CASCADE, related_name='exam_schedule_dates', null=True, blank=True)
    date = models.DateField()
    
class ExamScheduleData(models.Model):
    exam_schedule_date = models.ForeignKey(ExamScheduleDate, on_delete=models.CASCADE, related_name="exam_schedule_data")
    start_time = models.TimeField(default="")
    end_time = models.TimeField(default="")
    subject = models.CharField(max_length=30,default="")
    classes = models.CharField(max_length=20,default="") 
    room_number = models.CharField(max_length=10,default="") 
    type = models.CharField(max_length=15,default="")

    def __str__(self):
        return self.subject

    

# Create your models here.
