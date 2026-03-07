from rest_framework import serializers
from .models import StuentUniqueId, ProfessorUniqueId
from students.models import Student,StudentContactDetails,StudentSystemDetails
from professors.models import Professor,professorAdminEmployement

class StudentUniqueIdSerializer(serializers.ModelSerializer):

    student = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.select_related(
            'contact_details',
            'system_details'
        ),
        write_only=True
    )

    class Meta:
        model = StuentUniqueId
        fields = '__all__'
    
    
    def create(self, validated_data):
        student = validated_data.pop('student')
        student_contact_details = student.contact_details
        student_system_details = student.system_details
        validated_data.update({
            'student_id': student_system_details.id,
            'personal_id': student_system_details.student_personal_id,
            'email': student_contact_details.email,
            'phone_number': student_contact_details.mobile,
        })
        return super().create(validated_data)

    def validate_student(self, student):
        if StuentUniqueId.objects.filter(
            email=student.contact_details.email,
            student_id=student.system_details.student_personal_id,
            phone_number=student.contact_details.mobile,
        ).exists():
            raise serializers.ValidationError(
                "Unique ID already created for this student."
            )
        return student

        

class ProfessorUniqueIdSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessorUniqueId
        fields = '__all__'