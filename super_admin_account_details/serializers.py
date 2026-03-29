from rest_framework import serializers

from .models import SuperAdminAccountDetail


class SuperAdminAccountDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuperAdminAccountDetail
        fields = [
            'id',
            'institute',
            'account_holder_name',
            'bank_name',
            'account_number',
            'ifsc_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'institute', 'created_at', 'updated_at']

    def validate_account_holder_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Account holder name is required.')
        return value

    def validate_bank_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Bank name is required.')
        return value

    def validate_account_number(self, value):
        return value.strip()

    def validate_ifsc_code(self, value):
        return value.strip().upper()

    def create(self, validated_data):
        validated_data['institute'] = self.context['institute']
        return super().create(validated_data)
