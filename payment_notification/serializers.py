from rest_framework import serializers

from professors.models import Professor

from .models import PaymentNotification


class EncryptedDecimalField(serializers.DecimalField):
    def to_representation(self, value):
        return super().to_representation(value)


class EncryptedDateField(serializers.DateField):
    def to_representation(self, value):
        if isinstance(value, str):
            return value
        return super().to_representation(value)

class PaymentNotificationSerializer(serializers.ModelSerializer):
    professor = serializers.PrimaryKeyRelatedField(
        queryset=Professor.objects.all(),
        required=True,
        allow_null=False,
    )
    professor_name = serializers.CharField(source='professor.name', read_only=True)
    department = serializers.SerializerMethodField()
    final_amount = EncryptedDecimalField(max_digits=12, decimal_places=2)
    payment_month = serializers.RegexField(regex=r'^\d{4}-\d{2}$')
    payment_date = EncryptedDateField()
    approved_leaves = serializers.IntegerField(min_value=0)

    class Meta:
        model = PaymentNotification
        fields = [
            'id',
            'institute',
            'professor',
            'professor_name',
            'department',
            'account_holder_name',
            'bank_name',
            'account_number',
            'ifsc_code',
            'final_amount',
            'payment_month',
            'payment_date',
            'approved_leaves',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'institute',
            'professor_name',
            'department',
            'created_at',
            'updated_at',
        ]

    def get_department(self, obj):
        experience = getattr(obj.professor, 'experience', None)
        return getattr(experience, 'department', None)

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

    def validate_payment_month(self, value):
        return value.strip()

    def validate(self, attrs):
        professor = attrs.get('professor') or getattr(self.instance, 'professor', None)
        payment_month = attrs.get('payment_month') or getattr(self.instance, 'payment_month', None)
        institute = self.context['institute']

        if professor and payment_month:
            queryset = PaymentNotification.objects.filter(
                institute=institute,
                professor=professor,
                payment_month_key=payment_month,
            )
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    'Payment notification already exists for this professor and month.'
                )

        return attrs

    def _normalize_storage_values(self, validated_data):
        if 'final_amount' in validated_data:
            validated_data['final_amount'] = format(validated_data['final_amount'], 'f')
        if 'payment_date' in validated_data:
            validated_data['payment_date'] = validated_data['payment_date'].isoformat()
        if 'approved_leaves' in validated_data:
            validated_data['approved_leaves'] = str(validated_data['approved_leaves'])
        return validated_data

    def create(self, validated_data):
        validated_data = self._normalize_storage_values(validated_data)
        validated_data['institute'] = self.context['institute']
        validated_data['payment_month_key'] = validated_data['payment_month']
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._normalize_storage_values(validated_data)
        if 'payment_month' in validated_data:
            validated_data['payment_month_key'] = validated_data['payment_month']
        return super().update(instance, validated_data)
