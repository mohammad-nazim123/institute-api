from django.utils import timezone
from rest_framework import serializers

from .models import ArchiveRecord


class ArchiveRecordSerializer(serializers.ModelSerializer):
    institute = serializers.IntegerField(source='institute_id', read_only=True)

    class Meta:
        model = ArchiveRecord
        fields = [
            'id',
            'institute',
            'entity_type',
            'source_id',
            'name',
            'archived_data',
            'archived_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'institute',
            'entity_type',
            'source_id',
            'archived_at',
            'updated_at',
        ]
        extra_kwargs = {
            'name': {'required': False, 'allow_blank': True},
            'archived_data': {'required': False},
        }

    def update(self, instance, validated_data):
        for field in ('name', 'archived_data'):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.updated_at = timezone.now()
        instance.save(update_fields=['name', 'archived_data', 'updated_at'])
        return instance


class ArchiveCreateSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=ArchiveRecord.ENTITY_CHOICES)
    source_id = serializers.IntegerField(required=False, min_value=1)
    id = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        source_id = attrs.get('source_id') or attrs.get('id')
        if not source_id:
            raise serializers.ValidationError({'source_id': ['This field is required.']})
        attrs['source_id'] = source_id
        return attrs
