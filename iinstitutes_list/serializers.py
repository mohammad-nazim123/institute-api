from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Institute
from collections import OrderedDict


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
    all students, professors, courses, and schedules.
    Uses SerializerMethodField with lazy imports to avoid circular imports.
    """
    students = serializers.SerializerMethodField()
    professors = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    weekly_schedule_days = serializers.SerializerMethodField()
    exam_schedule_dates = serializers.SerializerMethodField()

    class Meta:
        model = Institute
        fields = ['id', 'name', 'event_status', 'event_timer_end',
                  'students', 'professors', 'courses',
                  'weekly_schedule_days', 'exam_schedule_dates']

    def get_students(self, obj):
        from students.serializers import StudentSerializer
        return StudentSerializer(obj.students.all(), many=True).data

    def get_professors(self, obj):
        from professors.serializers import ProfessorSerializer
        return ProfessorSerializer(obj.professors.all(), many=True).data

    def get_courses(self, obj):
        from syllabus.serializers import CourseSerializer
        return CourseSerializer(obj.courses.all(), many=True).data

    def get_weekly_schedule_days(self, obj):
        from schedules.serializers import WeeklyScheduleDaySerializer
        return WeeklyScheduleDaySerializer(obj.weekly_schedule_days.all(), many=True).data

    def get_exam_schedule_dates(self, obj):
        from schedules.serializers import ExamScheduleDateSerializer
        return ExamScheduleDateSerializer(obj.exam_schedule_dates.all(), many=True).data

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

        # Convert weekly schedules to dict keyed by day
        weekly_dict = OrderedDict()
        for schedule in data.get('weekly_schedule_days', []):
            key = schedule.get('day', f"id_{schedule.get('id', 'unknown')}")
            weekly_dict[key] = schedule

        # Convert exam schedules to dict keyed by date
        exam_dict = OrderedDict()
        for schedule in data.get('exam_schedule_dates', []):
            key = str(schedule.get('date', f"id_{schedule.get('id', 'unknown')}"))
            exam_dict[key] = schedule

        return OrderedDict([
            ('id', data['id']),
            ('name', data['name']),
            ('event_status', data.get('event_status', 'active')),
            ('event_timer_end', data.get('event_timer_end')),
            ('students', students_dict),
            ('professors', professors_dict),
            ('courses', courses_dict),
            ('weekly_schedules', weekly_dict),
            ('exam_schedules', exam_dict),
        ])