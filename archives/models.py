from django.db import models
from django.utils import timezone


class ArchiveRecord(models.Model):
    ENTITY_STUDENT = 'student'
    ENTITY_PROFESSOR = 'professor'
    ENTITY_CHOICES = [
        (ENTITY_STUDENT, 'Student'),
        (ENTITY_PROFESSOR, 'Professor'),
    ]

    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='archives',
    )
    entity_type = models.CharField(
        max_length=20,
        choices=ENTITY_CHOICES,
    )
    source_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=100, default='', db_index=True)
    archived_data = models.JSONField(default=dict)
    archived_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-archived_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['institute', 'entity_type', 'source_id'],
                name='uniq_archive_institute_entity_source',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'entity_type'], name='archive_inst_entity_idx'),
            models.Index(fields=['institute', 'source_id'], name='archive_inst_source_idx'),
        ]

    def __str__(self):
        return f'{self.entity_type}:{self.source_id} - {self.name}'
