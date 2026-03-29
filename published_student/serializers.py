from django.utils import timezone
from rest_framework import serializers

from .models import PublishedStudent


class PublishedStudentSerializer(serializers.ModelSerializer):
    institute = serializers.IntegerField(source='institute_id', read_only=True)
    student_id = serializers.IntegerField(source='source_student_id', read_only=True)

    class Meta:
        model = PublishedStudent
        fields = [
            'id',
            'institute',
            'student_id',
            'name',
            'student_data',
            'subjects_assigned',
            'published_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'institute',
            'student_id',
            'published_at',
            'updated_at',
        ]
        extra_kwargs = {
            'name': {'required': False, 'allow_blank': True},
            'student_data': {'required': False},
            'subjects_assigned': {'required': False},
        }

    def update(self, instance, validated_data):
        for field in ('name', 'student_data', 'subjects_assigned'):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.updated_at = timezone.now()
        instance.save(update_fields=['name', 'student_data', 'subjects_assigned', 'updated_at'])
        return instance
