import math

from rest_framework import serializers

from .models import PublishedObtainedMarks


class PublishedExamResultSerializer(serializers.ModelSerializer):
    published_exam_data_id = serializers.IntegerField(read_only=True)
    published_student_id = serializers.IntegerField(read_only=True)
    student_id = serializers.IntegerField(source='published_student.source_student_id', read_only=True)
    student_name = serializers.CharField(source='published_student.name', read_only=True)
    student_personal_id = serializers.CharField(source='published_student.student_personal_id', read_only=True)
    source_exam_data_id = serializers.IntegerField(source='published_exam_data.source_exam_data_id', read_only=True)
    source_obtained_marks_id = serializers.IntegerField(read_only=True)
    subject = serializers.CharField(source='published_exam_data.subject', read_only=True)
    class_name = serializers.CharField(source='published_exam_data.class_name', read_only=True)
    branch = serializers.CharField(source='published_exam_data.branch', read_only=True)
    academic_term = serializers.CharField(source='published_exam_data.academic_term', read_only=True)
    exam_type = serializers.CharField(source='published_exam_data.exam_type', read_only=True)
    exam_date = serializers.DateField(source='published_exam_data.date', read_only=True)
    duration = serializers.IntegerField(source='published_exam_data.duration', read_only=True)
    total_marks = serializers.IntegerField(source='published_exam_data.total_marks', read_only=True)
    pass_marks = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = PublishedObtainedMarks
        fields = [
            'id',
            'published_exam_data_id',
            'published_student_id',
            'student_id',
            'student_name',
            'student_personal_id',
            'source_exam_data_id',
            'source_obtained_marks_id',
            'subject',
            'class_name',
            'branch',
            'academic_term',
            'exam_type',
            'exam_date',
            'duration',
            'total_marks',
            'pass_marks',
            'obtained_marks',
            'status',
            'published_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_pass_marks(self, obj):
        total_marks = obj.published_exam_data.total_marks or 0
        return math.ceil(total_marks * 0.4) if total_marks else 0

    def get_status(self, obj):
        pass_marks = self.get_pass_marks(obj)
        return 'Pass' if obj.obtained_marks >= pass_marks else 'Fail'
