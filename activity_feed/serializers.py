from rest_framework import serializers

from .models import ActivityEvent


class ActivityEventSerializer(serializers.ModelSerializer):
    actor_label = serializers.SerializerMethodField()
    entity_label = serializers.SerializerMethodField()

    class Meta:
        model = ActivityEvent
        fields = [
            'id',
            'actor_name',
            'actor_role',
            'actor_access_control',
            'actor_source',
            'actor_label',
            'action',
            'entity_type',
            'entity_id',
            'entity_name',
            'entity_label',
            'title',
            'description',
            'details',
            'occurred_at',
        ]

    def get_actor_label(self, obj):
        return ' - '.join(value for value in [obj.actor_name, obj.actor_role] if value)

    def get_entity_label(self, obj):
        return obj.entity_name or obj.entity_type.replace('_', ' ').title()
