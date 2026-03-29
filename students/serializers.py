from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Student, StudentEducationDetails, StudentContactDetails, StudentAdmissionDetails, StudentCourseAssignment, StudentFeeDetails, StudentSystemDetails, SubjectsAssigned
from django.db import transaction
from iinstitutes_list.models import Institute
from institute_api.mixins import OptionalAndBlankMixin


class StudentEducationDetailsSerializer(OptionalAndBlankMixin, ModelSerializer):
    class Meta:
        model = StudentEducationDetails
        fields = '__all__'
        extra_kwargs = {
            "student": {"write_only": True, "required": False}
        }


class StudentContactDetailsSerializer(OptionalAndBlankMixin, ModelSerializer):
    class Meta:
        model = StudentContactDetails
        fields = '__all__'
        extra_kwargs = {
            "student": {"write_only": True, "required": False},
            "email": {"validators": []}
        }


class StudentAdmissionDetailsSerializer(OptionalAndBlankMixin, ModelSerializer):
    class Meta:
        model = StudentAdmissionDetails
        fields = '__all__'
        extra_kwargs = {
            "student": {"write_only": True, "required": False}
        }


class StudentCourseAssignmentSerializer(OptionalAndBlankMixin, ModelSerializer):
    class Meta:
        model = StudentCourseAssignment
        fields = '__all__'
        extra_kwargs = {
            "student": {"write_only": True, "required": False}
        }


class StudentFeeDetailsSerializer(OptionalAndBlankMixin, ModelSerializer):
    class Meta:
        model = StudentFeeDetails
        fields = '__all__'
        extra_kwargs = {
            "student": {"write_only": True, "required": False}
        }


class StudentSystemDetailsSerializer(OptionalAndBlankMixin, ModelSerializer):
    class Meta:
        model = StudentSystemDetails
        fields = '__all__'
        extra_kwargs = {
            "student": {"write_only": True, "required": False}
        }


class SubjectsAssignedSerializer(OptionalAndBlankMixin, ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].required = True
        self.fields['subject'].allow_blank = False
        self.fields['unit'].required = True
        self.fields['unit'].allow_blank = False

    class Meta:
        model = SubjectsAssigned
        fields = '__all__'
        extra_kwargs = {
            "student": {"required": True}
        }

    def validate(self, attrs):
        if self.instance is None or not self.partial:
            if not attrs.get('subject'):
                raise serializers.ValidationError({"subject": ["This field is required."]})
            if not attrs.get('unit'):
                raise serializers.ValidationError({"unit": ["This field is required."]})
        return attrs


class StudentSerializer(OptionalAndBlankMixin, ModelSerializer):
    education_details = StudentEducationDetailsSerializer(required=False)
    contact_details = StudentContactDetailsSerializer(required=False)
    admission_details = StudentAdmissionDetailsSerializer(required=False)
    course_assignment = StudentCourseAssignmentSerializer(source='course_assignments', required=False)
    fee_details = StudentFeeDetailsSerializer(required=False)
    system_details = StudentSystemDetailsSerializer(required=False)

    class Meta:
        model = Student
        fields = '__all__'

    def create(self, validated_data):
        education_details_data = validated_data.pop('education_details', None)
        contact_details_data = validated_data.pop('contact_details', None)
        admission_details_data = validated_data.pop('admission_details', None)
        course_assignments_data = validated_data.pop('course_assignments', None)
        fee_details_data = validated_data.pop('fee_details', None)
        system_details_data = validated_data.pop('system_details', None)

        with transaction.atomic():
            student = Student.objects.create(**validated_data)

            if education_details_data:
                StudentEducationDetails.objects.create(student=student, **education_details_data)

            if contact_details_data:
                StudentContactDetails.objects.create(student=student, **contact_details_data)

            if admission_details_data:
                StudentAdmissionDetails.objects.create(student=student, **admission_details_data)

            if course_assignments_data:
                StudentCourseAssignment.objects.create(student=student, **course_assignments_data)

            if fee_details_data:
                StudentFeeDetails.objects.create(student=student, **fee_details_data)

            if system_details_data:
                StudentSystemDetails.objects.create(student=student, **system_details_data)

        # Refresh from DB to load the related objects for the response
        student.refresh_from_db()
        return student

    def validate(self, attrs):
        contact_details = attrs.get('contact_details')
        if contact_details and 'email' in contact_details:
            email = contact_details['email']
            qs = StudentContactDetails.objects.filter(email=email)
            if self.instance:
                qs = qs.exclude(student=self.instance)
            if qs.exists():
                raise serializers.ValidationError(
                    {"contact_details": {"email": ["student contact details with this email already exists."]}}
                )
        return attrs

    def update(self, instance, validated_data):
        education_details_data = validated_data.pop('education_details', None)
        contact_details_data = validated_data.pop('contact_details', None)
        admission_details_data = validated_data.pop('admission_details', None)
        course_assignments_data = validated_data.pop('course_assignments', None)
        fee_details_data = validated_data.pop('fee_details', None)
        system_details_data = validated_data.pop('system_details', None)

        with transaction.atomic():
            changed_fields = list(validated_data.keys())
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            if changed_fields:
                instance.save(update_fields=changed_fields)

            if education_details_data:
                if hasattr(instance, 'education_details'):
                    obj = instance.education_details
                    for attr, value in education_details_data.items():
                        setattr(obj, attr, value)
                    obj.save(update_fields=list(education_details_data.keys()))
                else:
                    StudentEducationDetails.objects.create(student=instance, **education_details_data)

            if contact_details_data:
                if hasattr(instance, 'contact_details'):
                    obj = instance.contact_details
                    for attr, value in contact_details_data.items():
                        setattr(obj, attr, value)
                    obj.save(update_fields=list(contact_details_data.keys()))
                else:
                    StudentContactDetails.objects.create(student=instance, **contact_details_data)

            if admission_details_data:
                if hasattr(instance, 'admission_details'):
                    obj = instance.admission_details
                    for attr, value in admission_details_data.items():
                        setattr(obj, attr, value)
                    obj.save(update_fields=list(admission_details_data.keys()))
                else:
                    StudentAdmissionDetails.objects.create(student=instance, **admission_details_data)

            if course_assignments_data:
                if hasattr(instance, 'course_assignments'):
                    obj = instance.course_assignments
                    for attr, value in course_assignments_data.items():
                        setattr(obj, attr, value)
                    obj.save(update_fields=list(course_assignments_data.keys()))
                else:
                    StudentCourseAssignment.objects.create(student=instance, **course_assignments_data)

            if fee_details_data:
                if hasattr(instance, 'fee_details'):
                    obj = instance.fee_details
                    for attr, value in fee_details_data.items():
                        setattr(obj, attr, value)
                    obj.save(update_fields=list(fee_details_data.keys()))
                else:
                    StudentFeeDetails.objects.create(student=instance, **fee_details_data)

            if system_details_data:
                if hasattr(instance, 'system_details'):
                    obj = instance.system_details
                    for attr, value in system_details_data.items():
                        setattr(obj, attr, value)
                    obj.save(update_fields=list(system_details_data.keys()))
                else:
                    StudentSystemDetails.objects.create(student=instance, **system_details_data)

            return instance


class StudentIdLookUpSerializer(serializers.Serializer):
    student_personal_id = serializers.CharField(max_length=50)
    institute_name = serializers.CharField(max_length=255)
    email = serializers.CharField(max_length=100, required=False, allow_blank=True)
    mobile = serializers.CharField(max_length=15, required=False, allow_blank=True)

    def validate(self, attrs):
        student_personal_id = attrs.get('student_personal_id')
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
                student = Student.objects.get(
                    institute=institute,
                    contact_details__email=email,
                    system_details__student_personal_id=student_personal_id
                )
            elif mobile:
                student = Student.objects.get(
                    institute=institute,
                    contact_details__mobile=mobile,
                    system_details__student_personal_id=student_personal_id
                )
            else:
                raise serializers.ValidationError("Please provide either email or mobile.")
        except Student.DoesNotExist:
            raise serializers.ValidationError("Student not found in the selected institute.")

        attrs['student'] = student
        return attrs
