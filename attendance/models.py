from django.db import models
from django.utils import timezone
from students.models import Student
from professors.models import Professor


class AttendanceSubmission(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='student_attendance_submissions',
    )
    date = models.DateField()
    class_name = models.CharField(max_length=50, default="")
    branch = models.CharField(max_length=30, default="")
    year_semester = models.CharField(max_length=20, default="")
    marked_by = models.ForeignKey(Professor, on_delete=models.SET_NULL, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    attendance_time = models.TimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['institute', 'date', 'class_name', 'branch', 'year_semester'],
                name='uniq_student_attendance_submission',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'date'], name='att_sub_inst_date_idx'),
            models.Index(fields=['class_name', 'branch', 'date'], name='att_sub_class_branch_date_idx'),
        ]

    def __str__(self):
        return f"{self.class_name} - {self.branch} - {self.year_semester} - {self.date}"

    @staticmethod
    def current_local_time():
        return timezone.localtime(timezone.now()).timetz().replace(
            microsecond=0,
            tzinfo=None,
        )

    @staticmethod
    def time_from_datetime(value):
        if value is None:
            return None

        if timezone.is_aware(value):
            value = timezone.localtime(value)

        return value.timetz().replace(microsecond=0, tzinfo=None)

    @classmethod
    def derive_attendance_time(cls, submitted_at=None):
        return cls.time_from_datetime(submitted_at) or cls.current_local_time()

    def save(self, *args, **kwargs):
        derived_attendance_time = self.derive_attendance_time(self.submitted_at)
        if self.attendance_time != derived_attendance_time:
            self.attendance_time = derived_attendance_time

            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add('attendance_time')
                kwargs['update_fields'] = list(update_fields)

        super().save(*args, **kwargs)


class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    submission = models.ForeignKey(
        AttendanceSubmission,
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    status = models.BooleanField(default=False)  # True = Present, False = Absent

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'submission'],
                name='uniq_student_attendance_record',
            ),
        ]
        indexes = [
            models.Index(fields=['student', 'submission'], name='att_student_submission_idx'),
        ]

    @property
    def date(self):
        return self.submission.date if self.submission_id else None

    @property
    def class_name(self):
        return self.submission.class_name if self.submission_id else ''

    @property
    def branch(self):
        return self.submission.branch if self.submission_id else ''

    @property
    def year_semester(self):
        return self.submission.year_semester if self.submission_id else ''

    @property
    def marked_by(self):
        return self.submission.marked_by if self.submission_id else None

    @property
    def submitted_at(self):
        return self.submission.submitted_at if self.submission_id else None

    @property
    def attendance_time(self):
        return self.submission.attendance_time if self.submission_id else None

    def __str__(self):
        return f"{self.student.name} - {self.date} - {'Present' if self.status else 'Absent'}"

# Create your models here.
