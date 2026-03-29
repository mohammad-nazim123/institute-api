from rest_framework import serializers
from .models import ProfessorsPayments
from iinstitutes_list.models import Institute
from professors.models import Professor


class ProfessorsPaymentsSerializer(serializers.ModelSerializer):
    # Explicitly declared to override null=True on the model,
    # which prevents the "required + default" AssertionError in extra_kwargs
    institute = serializers.PrimaryKeyRelatedField(
        queryset=Institute.objects.all(), required=True, allow_null=False
    )
    professor = serializers.PrimaryKeyRelatedField(
        queryset=Professor.objects.all(), required=True, allow_null=False
    )
    month_year = serializers.CharField(max_length=7)

    class Meta:
        model = ProfessorsPayments
        fields = ['id', 'institute', 'professor', 'month_year', 'payment_date', 'payment_amount', 'payment_status']

    def validate(self, attrs):
        request = self.context.get('request')
        verified_institute = getattr(request, '_verified_institute', None) if request else None

        institute = attrs.get('institute') or getattr(self.instance, 'institute', None)
        professor = attrs.get('professor') or getattr(self.instance, 'professor', None)

        if verified_institute is not None:
            if institute is not None and institute != verified_institute:
                raise serializers.ValidationError({
                    'institute': ['Institute does not match the authenticated institute.'],
                })
            attrs['institute'] = verified_institute
            institute = verified_institute

        if institute is not None and professor is not None and professor.institute_id != institute.id:
            raise serializers.ValidationError({
                'professor': ['Professor does not belong to this institute.'],
            })

        return attrs
