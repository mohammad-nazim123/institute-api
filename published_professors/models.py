from django.db import models
from django.utils import timezone


class PublishedProfessor(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='published_professors',
    )
    source_professor_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=100, default="", db_index=True)
    email = models.EmailField(default="", db_index=True)
    professor_personal_id = models.CharField(max_length=30, default="", db_index=True)
    professor_data = models.JSONField(default=dict)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['institute', 'source_professor_id'],
                name='uniq_published_professor_institute_source',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'source_professor_id'], name='pub_prof_lookup_idx'),
            models.Index(fields=['institute', 'name'], name='pub_prof_name_idx'),
            models.Index(fields=['institute', 'email'], name='pub_prof_email_idx'),
            models.Index(fields=['institute', 'professor_personal_id'], name='pub_prof_pid_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.source_professor_id})'
