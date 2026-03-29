from django.utils import timezone
from rest_framework import serializers

from .models import PublishedProfessor


class PublishedProfessorSerializer(serializers.ModelSerializer):
    institute = serializers.IntegerField(source='institute_id', read_only=True)
    professor_id = serializers.IntegerField(source='source_professor_id', read_only=True)

    class Meta:
        model = PublishedProfessor
        fields = [
            'id',
            'institute',
            'professor_id',
            'name',
            'email',
            'professor_data',
            'published_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'institute',
            'professor_id',
            'published_at',
            'updated_at',
        ]
        extra_kwargs = {
            'name': {'required': False, 'allow_blank': True},
            'email': {'required': False, 'allow_blank': True},
            'professor_data': {'required': False},
        }

    def update(self, instance, validated_data):
        for field in ('name', 'email', 'professor_data'):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.updated_at = timezone.now()
        instance.save(update_fields=['name', 'email', 'professor_data', 'updated_at'])
        return instance


class PublishedProfessorIdLookupSerializer(serializers.Serializer):
    email = serializers.EmailField()
