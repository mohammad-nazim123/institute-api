from rest_framework import serializers
from .models import Professor, ProfessorAddress, ProfessorQualification, ProfessorExperience, professorAdminEmployement, professorClassAssigned
from iinstitutes_list.models import Institute


class ProfessorAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessorAddress
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class ProfessorQualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessorQualification
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class ProfessorExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessorExperience
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class professorAdminEmployementSerializer(serializers.ModelSerializer):
    class Meta:
        model = professorAdminEmployement
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class professorClassAssignedSerializer(serializers.ModelSerializer):
    class Meta:
        model = professorClassAssigned
        fields = '__all__'
        extra_kwargs = {
            'professor': {'write_only': True, 'required':False}
        }

class ProfessorSerializer(serializers.ModelSerializer):
    address = ProfessorAddressSerializer(required=False)
    qualification = ProfessorQualificationSerializer(many=True,required=False)
    experience = ProfessorExperienceSerializer(required=False)
    admin_employement = professorAdminEmployementSerializer(required=False)
    class_assigned = professorClassAssignedSerializer(required=False)
    class Meta:
        model = Professor
        fields = '__all__'

    def create(self, validated_data):
        address_data = validated_data.pop('address', None)
        qualification_data = validated_data.pop('qualification', [])
        experience_data = validated_data.pop('experience', None)
        admin_employement_data = validated_data.pop('admin_employement', None)
        class_assigned_data = validated_data.pop('class_assigned', None)
        
        professor = Professor.objects.create(**validated_data)
        
        if address_data:
            ProfessorAddress.objects.create(professor=professor, **address_data)
        
        for qual in qualification_data:
            ProfessorQualification.objects.create(professor=professor, **qual)
        
        if experience_data:
            ProfessorExperience.objects.create(professor=professor, **experience_data)
        
        if admin_employement_data:
            professorAdminEmployement.objects.create(professor=professor, **admin_employement_data)
        
        if class_assigned_data:
            professorClassAssigned.objects.create(professor=professor, **class_assigned_data)
        
        return professor

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

        # Resolve institute
        try:
            institute = Institute.objects.get(name=institute_name)
        except Institute.DoesNotExist:
            raise serializers.ValidationError("Institute not found.")

        try:
            if email:
                professor = Professor.objects.get(
                    institute=institute,
                    email=email,
                    admin_employement__personal_id=personal_id
                )
            elif mobile:
                professor = Professor.objects.get(
                    institute=institute,
                    phone_number=mobile,
                    admin_employement__personal_id=personal_id
                )
            else:
                raise serializers.ValidationError("Either email or mobile is required.")

            self.instance = professor
            return attrs

        except Professor.DoesNotExist:
            raise serializers.ValidationError(
                "Professor not found in the selected institute."
            )
