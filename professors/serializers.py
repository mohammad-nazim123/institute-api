from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import serializers

from institute_api.mixins import OptionalAndBlankMixin

from .models import (
    Professor,
    ProfessorAddress,
    ProfessorQualification,
    ProfessorExperience,
    professorAdminEmployement,
    professorClassAssigned,
)

class ProfessorAddressSerializer(OptionalAndBlankMixin, serializers.ModelSerializer):
    class Meta:
        model = ProfessorAddress
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class ProfessorQualificationSerializer(OptionalAndBlankMixin, serializers.ModelSerializer):
    class Meta:
        model = ProfessorQualification
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class ProfessorExperienceSerializer(OptionalAndBlankMixin, serializers.ModelSerializer):
    class Meta:
        model = ProfessorExperience
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class professorAdminEmployementSerializer(OptionalAndBlankMixin, serializers.ModelSerializer):
    class Meta:
        model = professorAdminEmployement
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class professorClassAssignedSerializer(OptionalAndBlankMixin, serializers.ModelSerializer):
    class Meta:
        model = professorClassAssigned
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class ProfessorSerializer(OptionalAndBlankMixin, serializers.ModelSerializer):
    address = ProfessorAddressSerializer(required=False)
    qualification = ProfessorQualificationSerializer(many=True,required=False)
    experience = ProfessorExperienceSerializer(required=False)
    admin_employement = professorAdminEmployementSerializer(required=False)
    class_assigned = professorClassAssignedSerializer(required=False)

    class Meta:
        model = Professor
        fields = '__all__'
        extra_kwargs = {
            'institute': {'required': False},
        }

    def _verified_institute(self):
        request = self.context.get('request')
        return getattr(request, '_verified_institute', None) if request is not None else None

    def _get_related_instance(self, professor, attr_name):
        try:
            return getattr(professor, attr_name)
        except ObjectDoesNotExist:
            return None

    def _upsert_one_to_one(self, model_class, professor, attr_name, data):
        if data is None:
            return

        instance = self._get_related_instance(professor, attr_name)
        if instance is None:
            model_class.objects.create(professor=professor, **data)
            return

        for field, value in data.items():
            setattr(instance, field, value)
        instance.save(update_fields=list(data.keys()))

    def create(self, validated_data):
        institute = self._verified_institute() or validated_data.pop('institute', None)
        address_data = validated_data.pop('address', None)
        qualification_data = validated_data.pop('qualification', [])
        experience_data = validated_data.pop('experience', None)
        admin_employement_data = validated_data.pop('admin_employement', None)
        class_assigned_data = validated_data.pop('class_assigned', None)

        if institute is not None:
            validated_data['institute'] = institute

        with transaction.atomic():
            professor = Professor.objects.create(**validated_data)

            if address_data:
                ProfessorAddress.objects.create(professor=professor, **address_data)

            if qualification_data:
                ProfessorQualification.objects.bulk_create([
                    ProfessorQualification(professor=professor, **qual)
                    for qual in qualification_data
                ])

            if experience_data:
                ProfessorExperience.objects.create(professor=professor, **experience_data)

            if admin_employement_data:
                professorAdminEmployement.objects.create(professor=professor, **admin_employement_data)

            if class_assigned_data:
                professorClassAssigned.objects.create(professor=professor, **class_assigned_data)

        return professor

    def update(self, instance, validated_data):
        validated_data.pop('institute', None)
        address_data = validated_data.pop('address', None)
        qualification_data = validated_data.pop('qualification', None)
        experience_data = validated_data.pop('experience', None)
        admin_employement_data = validated_data.pop('admin_employement', None)
        class_assigned_data = validated_data.pop('class_assigned', None)

        with transaction.atomic():
            changed_fields = list(validated_data.keys())
            for field, value in validated_data.items():
                setattr(instance, field, value)
            if changed_fields:
                instance.save(update_fields=changed_fields)

            self._upsert_one_to_one(ProfessorAddress, instance, 'address', address_data)
            self._upsert_one_to_one(ProfessorExperience, instance, 'experience', experience_data)
            self._upsert_one_to_one(
                professorAdminEmployement,
                instance,
                'admin_employement',
                admin_employement_data,
            )
            self._upsert_one_to_one(
                professorClassAssigned,
                instance,
                'class_assigned',
                class_assigned_data,
            )

            if qualification_data is not None:
                ProfessorQualification.objects.filter(professor=instance).delete()
                if qualification_data:
                    ProfessorQualification.objects.bulk_create([
                        ProfessorQualification(professor=instance, **qualification)
                        for qualification in qualification_data
                    ])

        return instance

class ProfessorIdLookUpSerializer(serializers.Serializer):
    personal_id = serializers.CharField(max_length=50)
    institute_name = serializers.CharField(max_length=255)
    email = serializers.CharField(max_length=100, required=False, allow_blank=True)
    mobile = serializers.CharField(max_length=15, required=False, allow_blank=True)

    def validate(self, attrs):
        personal_id = attrs.get('personal_id')
        institute_name = attrs.get('institute_name')
        email = attrs.get('email')
        mobile = attrs.get('mobile')

        try:
            filters = {
                'institute__institute_name': institute_name,
                'admin_employement__personal_id': personal_id,
            }
            if email:
                filters['email'] = email
            elif mobile:
                filters['phone_number'] = mobile
            else:
                raise serializers.ValidationError("Either email or mobile is required.")

            professor = Professor.objects.only('id').get(**filters)
            self.instance = professor
            return attrs
        except Professor.DoesNotExist:
            raise serializers.ValidationError(
                "Professor not found in the selected institute."
            )
