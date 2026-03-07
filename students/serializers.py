from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Student, StudentEducationDetails, StudentContactDetails, StudentCourseDetails, StudentAdmissionDetails, StudentCourseAssignment, StudentFeeDetails, StudentSystemDetails, SubjectsAssigned
from django.db import transaction
from iinstitutes_list.models import Institute

class StudentEducationDetailsSerializer(ModelSerializer):
    class Meta:
        model = StudentEducationDetails 
        fields = '__all__'
        extra_kwargs = {
            "student":{ "write_only": True, "required": False }
        }

class StudentContactDetailsSerializer(ModelSerializer):
    class Meta:
        model = StudentContactDetails
        fields = '__all__'
        extra_kwargs = {
            "student":{ "write_only": True, "required": False }
        }

class StudentCourseDetailsSerializer(ModelSerializer):
    class Meta:
        model = StudentCourseDetails
        fields = '__all__'
        extra_kwargs = {
            "student":{ "write_only": True, "required": False }
        }

class StudentAdmissionDetailsSerializer(ModelSerializer):
    class Meta:
        model = StudentAdmissionDetails
        fields = '__all__'
        extra_kwargs = {
            "student":{ "write_only": True, "required": False }
        }

class StudentCourseAssignmentSerializer(ModelSerializer):
    class Meta:
        model = StudentCourseAssignment
        fields = '__all__'
        extra_kwargs = {
            "student":{ "write_only": True, "required": False }
        }
class StudentFeeDetailsSerializer(ModelSerializer):
    class Meta:
        model = StudentFeeDetails
        fields = '__all__'
        extra_kwargs = {
            "student":{ "write_only":True, "required": False }
        }
    

class StudentSystemDetailsSerializer(ModelSerializer):
    class Meta:
        model = StudentSystemDetails
        fields = '__all__'
        extra_kwargs = {
            "student":{ "write_only": True, "required": False }
        }

class SubjectsAssignedSerializer(ModelSerializer):
    class Meta:
        model = SubjectsAssigned
        fields = '__all__'
        extra_kwargs = {
            "student": {"required": True}
        }


class StudentSerializer(ModelSerializer):
    education_details = StudentEducationDetailsSerializer(required = False)
    contact_details = StudentContactDetailsSerializer(required = False)
    course_details = StudentCourseDetailsSerializer(required = False)
    admission_details = StudentAdmissionDetailsSerializer(required = False)
    course_assignment = StudentCourseAssignmentSerializer(read_only = True)
    fee_details = StudentFeeDetailsSerializer(required = False)
    system_details = StudentSystemDetailsSerializer(required = False)

    class Meta:
        model = Student
        fields = '__all__'

    def create(self, validated_data):
        education_details_data = validated_data.pop('education_details',None)
        contact_details_data = validated_data.pop('contact_details',None)
        course_details_data = validated_data.pop('course_details',None)
        admission_details_data = validated_data.pop('admission_details',None)
        course_assignment_data = validated_data.pop('course_assignment',None)
        fee_details_data = validated_data.pop('fee_details',None)
        system_details_data = validated_data.pop('system_details',None)
    
        student = Student.objects.create(**validated_data)

        if education_details_data:
            StudentEducationDetails.objects.create(student=student, **education_details_data)
        
        if contact_details_data:
            StudentContactDetails.objects.create(student=student, **contact_details_data)

        
        if course_details_data:
            StudentCourseDetails.objects.create(student=student, **course_details_data)

        if admission_details_data:
            StudentAdmissionDetails.objects.create(student=student, **admission_details_data)

        if course_assignment_data:
            StudentCourseAssignment.objects.create(student=student, **course_assignment_data)

        if fee_details_data:
            StudentFeeDetails.objects.create(student=student, **fee_details_data)

        if system_details_data:
            StudentSystemDetails.objects.create(student=student, **system_details_data)

        # Refresh from DB to load the related objects for the response
        student.refresh_from_db()
        return student

    def update(self, instance, validated_data):
        # 1. Pop the nested data
        fee_details_data = validated_data.pop('fee_details', None)

        with transaction.atomic():
            # 2. Update the main Student instance
            # This updates all direct fields on the Student model
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # 3. Handle the nested Fee Details
            if fee_details_data:
                # Check if the student already has fee details
                if hasattr(instance, 'fee_details'):
                    # Update existing fee details
                    fee_instance = instance.fee_details
                    for attr, value in fee_details_data.items():
                        setattr(fee_instance, attr, value)
                    fee_instance.save()
                else:
                    # Create new fee details if they didn't exist before
                    StudentFeeDetails.objects.create(student=instance, **fee_details_data)

            return instance

class CourseSerializer(ModelSerializer):
    class Meta:
        model = StudentCourseDetails
        fields = ['id','course_name']

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
            raise serializers.ValidationError(
                "Student not found in the selected institute."
            )

        attrs['student'] = student
        return attrs

