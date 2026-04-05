from rest_framework import serializers

from iinstitutes_list.models import Institute

from .models import SubordinateAccess, SubordinateAccessVerificationRequest


class SubordinateAccessSerializer(serializers.ModelSerializer):
    institute = serializers.PrimaryKeyRelatedField(
        queryset=Institute.objects.all(),
        required=False,
        allow_null=False,
    )

    class Meta:
        model = SubordinateAccess
        fields = [
            'id',
            'institute',
            'post',
            'name',
            'access_control',
            'access_code',
            'is_active',
        ]
        extra_kwargs = {
            'id': {'read_only': True},
            'post': {'required': True, 'allow_blank': False},
            'name': {'required': True, 'allow_blank': False},
            'access_control': {'required': True, 'allow_blank': False},
            'access_code': {'required': True, 'allow_blank': False},
        }

    def validate(self, attrs):
        request = self.context.get('request')
        verified_institute = getattr(request, '_verified_institute', None) if request else None
        institute = attrs.get('institute') or getattr(self.instance, 'institute', None)

        if verified_institute is not None:
            if institute is not None and institute != verified_institute:
                raise serializers.ValidationError({
                    'institute': ['Institute does not match the authenticated institute.'],
                })
            attrs['institute'] = verified_institute

        return attrs


class SubordinateAccessVerificationRequestSerializer(serializers.ModelSerializer):
    institute_name = serializers.CharField(source='institute.institute_name', read_only=True)
    subordinate_name = serializers.CharField(source='subordinate_access.name', read_only=True)
    subordinate_post = serializers.CharField(source='subordinate_access.post', read_only=True)
    access_control = serializers.CharField(source='subordinate_access.access_control', read_only=True)
    is_active = serializers.BooleanField(source='subordinate_access.is_active', read_only=True)

    class Meta:
        model = SubordinateAccessVerificationRequest
        fields = [
            'id',
            'institute',
            'institute_name',
            'subordinate_access',
            'subordinate_name',
            'subordinate_post',
            'access_control',
            'is_active',
            'status',
            'requested_at',
            'reviewed_at',
        ]
        read_only_fields = [
            'id',
            'institute',
            'institute_name',
            'subordinate_access',
            'subordinate_name',
            'subordinate_post',
            'access_control',
            'is_active',
            'requested_at',
            'reviewed_at',
        ]

    def validate_status(self, value):
        if value not in {
            SubordinateAccessVerificationRequest.STATUS_APPROVED,
            SubordinateAccessVerificationRequest.STATUS_REJECTED,
        }:
            raise serializers.ValidationError('Status must be either approved or rejected.')
        return value
