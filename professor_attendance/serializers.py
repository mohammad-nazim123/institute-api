from rest_framework import serializers

from professors.models import Professor, ProfessorQualification

from .models import ProfessorAttendance, ProfessorLeave


class ProfessorDirectorySerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()
    specialization = serializers.SerializerMethodField()

    class Meta:
        model = Professor
        fields = [
            'id',
            'name',
            'department',
            'email',
            'phone_number',
            'specialization',
        ]

    def get_department(self, obj):
        experience = getattr(obj, 'experience', None)
        return getattr(experience, 'department', None)

    def get_specialization(self, obj):
        specialization = getattr(obj, 'primary_specialization', None)
        if specialization is not None:
            return specialization

        return (
            ProfessorQualification.objects
            .filter(professor=obj)
            .order_by('id')
            .values_list('specialization', flat=True)
            .first()
        )


class ProfessorAttendanceSerializer(serializers.ModelSerializer):
    professor_name = serializers.CharField(source='professor.name', read_only=True)
    department = serializers.SerializerMethodField()
    email = serializers.CharField(source='professor.email', read_only=True)
    phone_number = serializers.CharField(source='professor.phone_number', read_only=True)
    specialization = serializers.SerializerMethodField()

    class Meta:
        model = ProfessorAttendance
        fields = [
            'id',
            'professor',
            'professor_name',
            'department',
            'email',
            'phone_number',
            'specialization',
            'date',
            'status',
            'attendance_time',
        ]

    def get_department(self, obj):
        experience = getattr(obj.professor, 'experience', None)
        return getattr(experience, 'department', None)

    def get_specialization(self, obj):
        specialization = getattr(obj, 'primary_specialization', None)
        if specialization is not None:
            return specialization

        return (
            ProfessorQualification.objects
            .filter(professor=obj.professor)
            .order_by('id')
            .values_list('specialization', flat=True)
            .first()
        )

    def validate_professor(self, professor):
        institute = self.context['institute']
        if professor.institute_id != institute.id:
            raise serializers.ValidationError(
                'Professor not found in the authenticated institute.'
            )
        return professor

    def validate(self, attrs):
        professor = attrs.get('professor') or getattr(self.instance, 'professor', None)
        date = attrs.get('date') or getattr(self.instance, 'date', None)
        institute = self.context['institute']

        if professor and date:
            queryset = ProfessorAttendance.objects.filter(
                institute=institute,
                professor=professor,
                date=date,
            )
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    'Attendance already exists for this professor on this date.'
                )

        return attrs

    def create(self, validated_data):
        validated_data['institute'] = self.context['institute']
        return super().create(validated_data)


class ProfessorLeaveSerializer(serializers.ModelSerializer):
    professor_name = serializers.CharField(source='professor.name', read_only=True)
    department = serializers.SerializerMethodField()
    email = serializers.CharField(source='professor.email', read_only=True)

    class Meta:
        model = ProfessorLeave
        fields = [
            'id',
            'professor',
            'professor_name',
            'department',
            'email',
            'date',
            'comment',
            'status',
        ]

    def get_department(self, obj):
        experience = getattr(obj.professor, 'experience', None)
        return getattr(experience, 'department', None)

    def validate_professor(self, professor):
        institute = self.context['institute']
        if professor.institute_id != institute.id:
            raise serializers.ValidationError(
                'Professor not found in the authenticated institute.'
            )
        return professor

    def validate_status(self, value):
        if value == 'rejected':
            return ProfessorLeave.STATUS_REJECT
        return value

    def validate(self, attrs):
        professor = attrs.get('professor') or getattr(self.instance, 'professor', None)
        date = attrs.get('date') or getattr(self.instance, 'date', None)
        institute = self.context['institute']

        if professor and date:
            queryset = ProfessorLeave.objects.filter(
                institute=institute,
                professor=professor,
                date=date,
            )
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    'Leave already exists for this professor on this date.'
                )

        return attrs

    def create(self, validated_data):
        validated_data['institute'] = self.context['institute']
        return super().create(validated_data)
