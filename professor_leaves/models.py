from datetime import time

from django.db import models
from django.utils import timezone


class ProfessorLeave(models.Model):
    class LeaveStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        CANCELLED = 'cancelled', 'Cancelled'

    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='professor_leaves',
    )
    published_professor = models.ForeignKey(
        'published_professors.PublishedProfessor',
        on_delete=models.CASCADE,
        related_name='leave_records',
    )
    professor_name = models.CharField(max_length=100, default="", blank=True)
    department = models.CharField(max_length=100, default="", blank=True)
    email = models.EmailField(default="", blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    current_time = models.TimeField(blank=True, null=True)
    reason = models.TextField(default='', blank=True)
    leaves_status = models.CharField(
        max_length=10,
        choices=LeaveStatus.choices,
        default=LeaveStatus.PENDING,
    )
    cancellation_reason = models.TextField(default='', blank=True)
    total_days = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['published_professor', 'start_date', 'end_date'],
                name='uniq_prof_leave_prof_date_range',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'start_date'], name='prof_leave_inst_start_idx'),
            models.Index(fields=['institute', 'published_professor'], name='prof_leave_inst_prof_idx'),
        ]

    def __str__(self):
        return f'{self.professor_name} - {self.start_date} to {self.end_date}'

    @staticmethod
    def _current_local_time():
        return timezone.localtime(timezone.now()).time().replace(microsecond=0, tzinfo=None)

    def save(self, *args, **kwargs):
        if self.current_time is None:
            self.current_time = self._current_local_time()

        if self.start_date and self.end_date:
            self.total_days = (self.end_date - self.start_date).days + 1

        if self.leaves_status != self.LeaveStatus.CANCELLED:
            self.cancellation_reason = ''

        super().save(*args, **kwargs)


class InstituteTotalLeave(models.Model):
    institute = models.OneToOneField(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='professor_total_leave_setting',
    )
    total_leaves = models.PositiveIntegerField(default=0)
    session_start_month = models.PositiveSmallIntegerField(default=4)
    session_end_month = models.PositiveSmallIntegerField(default=3)
    opening_time = models.TimeField(default=time(8, 0))
    closing_time = models.TimeField(default=time(18, 0))

    def __str__(self):
        return f'{self.institute_id} - {self.total_leaves}'
