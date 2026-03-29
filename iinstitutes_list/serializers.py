from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Institute
from collections import OrderedDict
from students.serializers import StudentSerializer
from professors.serializers import ProfessorSerializer
from syllabus.serializers import CourseSerializer


class InstituteSerializer(ModelSerializer):
    class Meta:
        model = Institute
        fields = ['id', 'name', 'admin_key', 'event_status', 'event_timer_end']
        extra_kwargs = {
            'admin_key': {'read_only': True},
            'event_status': {'read_only': True},
            'event_timer_end': {'read_only': True},
        }


class InstituteVerifySerializer(serializers.Serializer):
    """Serializer for verifying institute access via name + admin_key."""
    name = serializers.CharField(max_length=255)
    admin_key = serializers.CharField(max_length=32)


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
        fields = ['id', 'name', 'event_status', 'event_timer_end',
                  'students', 'professors', 'courses']

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
            ('name', data['name']),
            ('event_status', data.get('event_status', 'active')),
            ('event_timer_end', data.get('event_timer_end')),
            ('students', students_dict),
            ('professors', professors_dict),
            ('courses', courses_dict),
        ])
