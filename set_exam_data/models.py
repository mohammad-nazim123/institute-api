from django.db import models
from iinstitutes_list.models import Institute
from students.models import Student


class ExamData(models.Model):
    """
    Flat exam data — no separate Class/Branch/Term tables.
    institute + class_name + branch + academic_term are stored directly
    on each row, exactly like weekly_exam_schedule.
    """
    institute = models.ForeignKey(
        Institute,
        on_delete=models.CASCADE,
        related_name='exam_data_flat',
        null=True,
        blank=True,
    )
    class_name = models.CharField(max_length=40, default="")
    branch = models.CharField(max_length=100, default="")
    academic_term = models.CharField(max_length=15, default="")
    subject = models.CharField(max_length=40, default="")
    exam_type = models.CharField(max_length=10, default="")
    date = models.DateField(null=True, blank=True)
    duration = models.IntegerField(default=0)
    total_marks = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.subject} - {self.class_name} / {self.branch} / {self.academic_term}"

    class Meta:
        indexes = [
            # Primary read index: filter by institute + hierarchy
            models.Index(
                fields=['institute', 'class_name', 'branch', 'academic_term'],
                name='examdata_inst_hierarchy_idx',
            ),
            # Secondary: filter by subject within a term
            models.Index(
                fields=['institute', 'class_name', 'branch', 'academic_term', 'subject'],
                name='examdata_inst_subj_idx',
            ),
        ]


class ObtainedMarks(models.Model):
    exam_data = models.ForeignKey(
        ExamData,
        on_delete=models.CASCADE,
        related_name='obtained_marks',
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='obtained_marks',
    )
    obtained_marks = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.student} - {self.obtained_marks} marks"

    class Meta:
        db_table = 'obtained_marks'
        indexes = [
            models.Index(fields=['exam_data', 'student'], name='obtmarks_examdata_student_idx'),
            models.Index(fields=['student'], name='obtmarks_student_idx'),
        ]
