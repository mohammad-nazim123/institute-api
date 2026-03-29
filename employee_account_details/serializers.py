from rest_framework import serializers

from professors.models import Professor

from .models import EmployeeAccountDetail


class EmployeeAccountDetailSerializer(serializers.ModelSerializer):
    professor_name = serializers.CharField(source='professor.name', read_only=True)
    professor = serializers.PrimaryKeyRelatedField(
        queryset=Professor.objects.all(),
        required=True,
        allow_null=False,
    )

    class Meta:
        model = EmployeeAccountDetail
        fields = [
            'id',
            'institute',
            'professor',
            'professor_name',
            'account_holder_name',
            'bank_name',
            'account_number',
            'ifsc_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'institute', 'professor_name', 'created_at', 'updated_at']

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

    def validate_professor(self, professor):
        institute = self.context['institute']
        if professor.institute_id != institute.id:
            raise serializers.ValidationError(
                'Professor does not belong to the authenticated institute.'
            )
        return professor

    def create(self, validated_data):
        validated_data['institute'] = self.context['institute']
        return super().create(validated_data)
