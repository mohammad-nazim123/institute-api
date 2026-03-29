from django.db import models
from django.utils import timezone


class PublishedWeeklySchedule(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='published_weekly_schedules',
    )
    class_name = models.CharField(max_length=50)
    branch = models.CharField(max_length=100)
    academic_term = models.CharField(max_length=50)
    schedule_data = models.JSONField(default=list)
    source_hash = models.CharField(max_length=64, default='')
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(
                fields=['institute', 'class_name', 'branch', 'academic_term'],
                name='pub_weekly_hierarchy_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institute', 'class_name', 'branch', 'academic_term'],
                name='uniq_pub_weekly_schedule',
            ),
        ]

    def __str__(self):
        return f'{self.class_name} / {self.branch} / {self.academic_term}'


class PublishedExamSchedule(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='published_exam_schedules',
    )
    class_name = models.CharField(max_length=50)
    branch = models.CharField(max_length=100)
    academic_term = models.CharField(max_length=50)
    schedule_data = models.JSONField(default=list)
    source_hash = models.CharField(max_length=64, default='')
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(
                fields=['institute', 'class_name', 'branch', 'academic_term'],
                name='pub_exam_hierarchy_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institute', 'class_name', 'branch', 'academic_term'],
                name='uniq_pub_exam_schedule',
            ),
        ]

    def __str__(self):
        return f'{self.class_name} / {self.branch} / {self.academic_term}'
