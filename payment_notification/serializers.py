from decimal import Decimal

from rest_framework import serializers

from professors.models import Professor

from .models import PaymentNotification


def get_related_or_none(instance, relation_name):
    try:
        return getattr(instance, relation_name)
    except Exception:
        return None


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
    employee_id = serializers.SerializerMethodField()
    gross_amount = EncryptedDecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
    )
    deducted_amount = EncryptedDecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
    )
    final_amount = EncryptedDecimalField(max_digits=12, decimal_places=2)
    payment_month = serializers.RegexField(regex=r'^\d{4}-\d{2}$')
    payment_date = EncryptedDateField()
    approved_leaves = serializers.IntegerField(min_value=0)
    status = serializers.ChoiceField(
        choices=PaymentNotification.Status.choices,
        required=False,
    )

    class Meta:
        model = PaymentNotification
        fields = [
            'id',
            'institute',
            'professor',
            'professor_name',
            'department',
            'employee_id',
            'account_holder_name',
            'bank_name',
            'account_number',
            'ifsc_code',
            'gross_amount',
            'deducted_amount',
            'final_amount',
            'payment_month',
            'payment_date',
            'approved_leaves',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'institute',
            'professor_name',
            'department',
            'employee_id',
            'created_at',
            'updated_at',
        ]

    def get_department(self, obj):
        experience = get_related_or_none(obj.professor, 'experience')
        return getattr(experience, 'department', None)

    def get_employee_id(self, obj):
        admin_employement = get_related_or_none(obj.professor, 'admin_employement')
        return getattr(admin_employement, 'employee_id', '')

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

    def validate_status(self, value):
        normalized_value = str(value or '').strip().lower()
        return normalized_value or PaymentNotification.Status.PENDING

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

        final_amount = attrs.get('final_amount')
        gross_amount = attrs.get('gross_amount')
        deducted_amount = attrs.get('deducted_amount')

        if gross_amount is None:
            if final_amount is not None:
                attrs['gross_amount'] = final_amount
            elif self.instance is None:
                attrs['gross_amount'] = Decimal('0.00')

        if deducted_amount is None and self.instance is None:
            attrs['deducted_amount'] = Decimal('0.00')

        attrs.setdefault(
            'status',
            getattr(self.instance, 'status', PaymentNotification.Status.PENDING),
        )

        return attrs

    def _normalize_storage_values(self, validated_data):
        if 'gross_amount' in validated_data:
            validated_data['gross_amount'] = format(validated_data['gross_amount'], 'f')
        if 'deducted_amount' in validated_data:
            validated_data['deducted_amount'] = format(validated_data['deducted_amount'], 'f')
        if 'final_amount' in validated_data:
            validated_data['final_amount'] = format(validated_data['final_amount'], 'f')
        if 'payment_date' in validated_data:
            validated_data['payment_date'] = validated_data['payment_date'].isoformat()
        if 'approved_leaves' in validated_data:
            validated_data['approved_leaves'] = str(validated_data['approved_leaves'])
        if 'status' in validated_data:
            validated_data['status'] = str(validated_data['status']).strip().lower()
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
