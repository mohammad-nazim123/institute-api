from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Institute
from collections import OrderedDict
from students.serializers import StudentSerializer
from professors.serializers import ProfessorSerializer
from syllabus.serializers import CourseSerializer


class InstituteSerializer(ModelSerializer):
    institute_name = serializers.CharField()

    class Meta:
        model = Institute
        fields = [
            'id',
            'institute_name',
            'super_admin_name',
            'admin_key',
            'event_status',
            'event_timer_end',
        ]
        extra_kwargs = {
            'admin_key': {'read_only': True},
            'event_status': {'read_only': True},
            'event_timer_end': {'read_only': True},
        }

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'institute_name' not in mutable_data and 'name' in mutable_data:
            mutable_data['institute_name'] = mutable_data['name']
        return super().to_internal_value(mutable_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['name'] = data['institute_name']
        return data


class InstituteVerifySerializer(serializers.Serializer):
    """Serializer for verifying institute access via name + admin_key."""
    institute_name = serializers.CharField(max_length=255, required=False, allow_blank=False)
    name = serializers.CharField(max_length=255, required=False, allow_blank=False)
    super_admin_name = serializers.CharField(max_length=255, required=False, allow_blank=False)
    admin_key = serializers.CharField(max_length=32)

    def validate(self, attrs):
        institute_name = attrs.get('institute_name') or attrs.get('name')
        if not institute_name:
            raise serializers.ValidationError({'institute_name': ['Institute name is required.']})

        admin_key = attrs.get('admin_key') or ''
        super_admin_name = attrs.get('super_admin_name')
        if len(admin_key) == 32 and not super_admin_name:
            raise serializers.ValidationError({
                'super_admin_name': ['Super admin name is required.'],
            })

        attrs['institute_name'] = institute_name
        return attrs


class InstituteDetailSerializer(ModelSerializer):
    """
    Produces a deeply nested dictionary for a single institute including
    all students, professors, and courses.
    Uses nested serializers so prefetched data can be rendered efficiently.
    """
    students = StudentSerializer(many=True, read_only=True)
    professors = ProfessorSerializer(many=True, read_only=True)
    courses = CourseSerializer(many=True, read_only=True)

    class Meta:
        model = Institute
        fields = [
            'id',
            'institute_name',
            'super_admin_name',
            'event_status',
            'event_timer_end',
            'students',
            'professors',
            'courses',
        ]

    def to_representation(self, instance):
        """Convert to nested dictionary keyed by entity name."""
        data = super().to_representation(instance)

        # Convert students list to dict keyed by student name
        students_dict = OrderedDict()
        for student in data.get('students', []):
            key = student.get('name', f"id_{student.get('id', 'unknown')}")
            students_dict[key] = student

        # Convert professors list to dict keyed by professor name
        professors_dict = OrderedDict()
        for professor in data.get('professors', []):
            key = professor.get('name', f"id_{professor.get('id', 'unknown')}")
            professors_dict[key] = professor

        # Convert courses list to dict keyed by course name
        courses_dict = OrderedDict()
        for course in data.get('courses', []):
            key = course.get('name', f"id_{course.get('id', 'unknown')}")
            courses_dict[key] = course

        return OrderedDict([
            ('id', data['id']),
            ('institute_name', data['institute_name']),
            ('name', data['institute_name']),
            ('super_admin_name', data.get('super_admin_name', '')),
            ('event_status', data.get('event_status', 'active')),
            ('event_timer_end', data.get('event_timer_end')),
            ('students', students_dict),
            ('professors', professors_dict),
            ('courses', courses_dict),
        ])
