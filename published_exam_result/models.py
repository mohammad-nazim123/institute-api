from django.db import models
from django.utils import timezone


class PublishedExamData(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='published_exam_data',
    )
    source_exam_data_id = models.PositiveBigIntegerField(unique=True)
    class_name = models.CharField(max_length=40, default='')
    branch = models.CharField(max_length=100, default='')
    academic_term = models.CharField(max_length=15, default='')
    subject = models.CharField(max_length=40, default='')
    exam_type = models.CharField(max_length=10, default='')
    date = models.DateField(null=True, blank=True)
    duration = models.IntegerField(default=0)
    total_marks = models.IntegerField(default=0)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'published_exam_data'
        indexes = [
            models.Index(
                fields=['institute', 'class_name', 'branch', 'academic_term', 'exam_type'],
                name='pub_exam_data_scope_idx',
            ),
            models.Index(
                fields=['institute', 'subject'],
                name='pub_exam_data_subject_idx',
            ),
        ]

    def __str__(self):
        return f'{self.subject} - {self.class_name} / {self.branch} / {self.academic_term}'


class PublishedObtainedMarks(models.Model):
    published_exam_data = models.ForeignKey(
        'published_exam_result.PublishedExamData',
        on_delete=models.CASCADE,
        related_name='published_obtained_marks',
    )
    published_student = models.ForeignKey(
        'published_student.PublishedStudent',
        on_delete=models.CASCADE,
        related_name='published_exam_results',
    )
    source_obtained_marks_id = models.PositiveBigIntegerField(unique=True)
    obtained_marks = models.IntegerField(default=0)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'published_obtained_marks'
        constraints = [
            models.UniqueConstraint(
                fields=['published_exam_data', 'published_student'],
                name='uniq_pub_exam_data_student',
            ),
        ]
        indexes = [
            models.Index(
                fields=['published_student'],
                name='pub_obt_marks_student_idx',
            ),
            models.Index(
                fields=['published_exam_data'],
                name='pub_obt_marks_exam_idx',
            ),
        ]

    def __str__(self):
        return f'{self.published_student.name} - {self.obtained_marks} marks'
