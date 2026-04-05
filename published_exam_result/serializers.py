from rest_framework import serializers

from .models import PublishedExamResult


class PublishedExamResultSerializer(serializers.ModelSerializer):
    institute = serializers.IntegerField(source='institute_id', read_only=True)
    published_student_id = serializers.IntegerField(read_only=True)
    student_id = serializers.IntegerField(source='source_student_id', read_only=True)

    class Meta:
        model = PublishedExamResult
        fields = [
            'id',
            'institute',
            'published_student_id',
            'student_id',
            'name',
            'student_personal_id',
            'exam_results',
            'published_at',
            'updated_at',
        ]
        read_only_fields = fields
