from django.db import transaction
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
            'card_design',
            'is_default',
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

    def validate_card_design(self, value):
        return value.strip().lower()

    def create(self, validated_data):
        institute = self.context['institute']
        validated_data['institute'] = institute

        if not SuperAdminAccountDetail.objects.filter(institute=institute).exists():
            validated_data['is_default'] = True

        with transaction.atomic():
            instance = super().create(validated_data)

            if instance.is_default:
                SuperAdminAccountDetail.objects.filter(
                    institute=institute
                ).exclude(pk=instance.pk).update(is_default=False)

        return instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            other_accounts = SuperAdminAccountDetail.objects.filter(
                institute=instance.institute
            ).exclude(pk=instance.pk)

            if instance.is_default:
                other_accounts.update(is_default=False)
            elif not other_accounts.filter(is_default=True).exists():
                instance.is_default = True
                instance.save(update_fields=['is_default', 'updated_at'])

        return instance
