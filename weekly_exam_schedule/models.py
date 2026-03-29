from django.db import models


class WeeklyScheduleDay(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='weekly_exam_schedule_days',
        null=True,
        blank=True,
    )
    day = models.CharField(max_length=15, default="")

    def __str__(self):
        return self.day


class WeeklyScheduleData(models.Model):
    weekly_schedule_day = models.ForeignKey(
        WeeklyScheduleDay,
        on_delete=models.CASCADE,
        related_name="weekly_schedule_data",
    )
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='weekly_schedule_data',
        null=True,
        blank=True,
    )
    class_name = models.CharField(max_length=50, default="")
    branch = models.CharField(max_length=100, default="")
    academic_term = models.CharField(max_length=50, default="")
    start_time = models.TimeField(default="")
    end_time = models.TimeField(default="")
    subject = models.CharField(max_length=30, default="")
    room_number = models.CharField(max_length=10, default="")
    professor = models.CharField(max_length=30, default="")

    class Meta:
        indexes = [
            models.Index(
                fields=['institute', 'class_name', 'branch', 'academic_term', 'weekly_schedule_day'],
                name='wsd_inst_hierarchy_idx',
            ),
        ]

    def __str__(self):
        return self.subject


class ExamScheduleDate(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='weekly_exam_schedule_dates',
        null=True,
        blank=True,
    )
    date = models.DateField()

    def __str__(self):
        return str(self.date)


class ExamScheduleData(models.Model):
    exam_schedule_date = models.ForeignKey(
        ExamScheduleDate,
        on_delete=models.CASCADE,
        related_name="exam_schedule_data",
    )
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='exam_schedule_data',
        null=True,
        blank=True,
    )
    class_name = models.CharField(max_length=50, default="")
    branch = models.CharField(max_length=100, default="")
    academic_term = models.CharField(max_length=50, default="")
    start_time = models.TimeField(default="")
    end_time = models.TimeField(default="")
    subject = models.CharField(max_length=30, default="")
    room_number = models.CharField(max_length=10, default="")
    type = models.CharField(max_length=15, default="")

    class Meta:
        indexes = [
            models.Index(
                fields=['institute', 'class_name', 'branch', 'academic_term', 'exam_schedule_date'],
                name='esd_inst_hierarchy_idx',
            ),
        ]

    def __str__(self):
        return self.subject
