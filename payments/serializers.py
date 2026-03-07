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
        fields = '__all__'