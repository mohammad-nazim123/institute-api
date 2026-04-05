from django.db import models
from django.utils import timezone


class PublishedExamResult(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='published_exam_results',
    )
    published_student = models.OneToOneField(
        'published_student.PublishedStudent',
        on_delete=models.CASCADE,
        related_name='published_exam_result',
    )
    source_student_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=100, default='', db_index=True)
    student_personal_id = models.CharField(max_length=50, default='', db_index=True)
    exam_results = models.JSONField(default=list)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['institute', 'source_student_id'],
                name='uniq_pub_exam_result_inst_source',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'source_student_id'], name='pub_exam_res_lookup_idx'),
            models.Index(fields=['institute', 'name'], name='pub_exam_res_name_idx'),
            models.Index(fields=['institute', 'student_personal_id'], name='pub_exam_res_pid_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.source_student_id})'
