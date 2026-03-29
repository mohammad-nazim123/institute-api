from django.db import models
from django.utils import timezone

from professors.models import Professor


class ProfessorAttendance(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='professor_attendance_records',
    )
    professor = models.ForeignKey(
        Professor,
        on_delete=models.CASCADE,
        related_name='professor_attendance_records',
    )
    date = models.DateField()
    status = models.BooleanField(default=False)
    attendance_time = models.TimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['professor', 'date'],
                name='uniq_prof_attendance_per_day',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'date'], name='prof_att_app_inst_date_idx'),
            models.Index(fields=['professor', 'date'], name='prof_att_app_prof_date_idx'),
        ]

    def __str__(self):
        return f"{self.professor.name} - {self.date} - {'Present' if self.status else 'Absent'}"

    @staticmethod
    def _current_local_time():
        return timezone.localtime(timezone.now()).time().replace(microsecond=0, tzinfo=None)

    def save(self, *args, **kwargs):
        previous = None
        if self.pk:
            previous = (
                type(self).objects
                .filter(pk=self.pk)
                .values('status', 'attendance_time')
                .first()
            )

        if self.attendance_time is None:
            self.attendance_time = self._current_local_time()
        elif previous and previous['status'] != self.status:
            if self.attendance_time == previous['attendance_time']:
                self.attendance_time = self._current_local_time()

        super().save(*args, **kwargs)


class ProfessorLeave(models.Model):
    STATUS_APPROVED = 'approved'
    STATUS_REJECT = 'reject'
    STATUS_CHOICES = [
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECT, 'Reject'),
    ]

    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='professor_leave_records',
    )
    professor = models.ForeignKey(
        Professor,
        on_delete=models.CASCADE,
        related_name='professor_leave_records',
    )
    date = models.DateField()
    comment = models.TextField(default='', blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_APPROVED)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['professor', 'date'],
                name='uniq_prof_leave_per_day',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'date'], name='prof_leave_app_inst_date_idx'),
            models.Index(fields=['institute', 'status'], name='prof_leave_app_inst_status_idx'),
            models.Index(fields=['professor', 'date'], name='prof_leave_app_prof_date_idx'),
        ]

    def __str__(self):
        return f"{self.professor.name} - {self.date} - {self.status}"
