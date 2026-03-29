import secrets
import string

from django.db import models
from django.utils import timezone


def generate_published_key():
    # Kept for migration compatibility; new reads use student_personal_id instead.
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(15))


class PublishedStudent(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='published_students',
    )
    source_student_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=100, default="", db_index=True)
    student_personal_id = models.CharField(max_length=50, default="", db_index=True)
    student_data = models.JSONField(default=dict)
    subjects_assigned = models.JSONField(default=list)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['institute', 'source_student_id'],
                name='uniq_published_student_institute_source',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'source_student_id'], name='pub_student_lookup_idx'),
            models.Index(fields=['institute', 'name'], name='pub_student_name_idx'),
            models.Index(fields=['institute', 'student_personal_id'], name='pub_student_pid_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.source_student_id})'
