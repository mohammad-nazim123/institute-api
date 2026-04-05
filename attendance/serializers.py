from rest_framework import serializers
from students.models import Student
from .models import Attendance


class StudentSerializer(serializers.ModelSerializer):
    """Minimal student representation for the GET /api/students/ endpoint."""

    class Meta:
        model = Student
        fields = ['id', 'name', 'gender', 'category']


class StudentAttendanceRecordSerializer(serializers.ModelSerializer):
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ['id', 'date', 'class_name', 'branch', 'year_semester', 'status', 'marked_by', 'marked_by_name']

    def get_marked_by_name(self, obj):
        return obj.marked_by.name if obj.marked_by else None


class StudentAttendanceListSerializer(serializers.ModelSerializer):
    attendance_records = StudentAttendanceRecordSerializer(source='attendances', many=True, read_only=True)

    class Meta:
        model = Student
        fields = ['id', 'name', 'gender', 'category', 'attendance_records']


class StudentAttendanceSummarySerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    total = serializers.IntegerField()
    percentage = serializers.IntegerField()


class AttendanceRecordSerializer(serializers.Serializer):
    """Represents a single student's attendance entry inside the bulk payload."""
    student_id = serializers.IntegerField()
    status = serializers.BooleanField()
    class_name = serializers.CharField(max_length=50, default='', required=False)
    branch = serializers.CharField(max_length=30, default='', required=False)
    year_semester = serializers.CharField(max_length=20, default='', required=False)


class MarkAttendanceSerializer(serializers.Serializer):
    """Top-level serializer for POST /api/attendance/mark/"""
    date = serializers.DateField()
    attendance = AttendanceRecordSerializer(many=True)

    def validate_attendance(self, value):
        if not value:
            raise serializers.ValidationError("Attendance list must not be empty.")
        return value


class AttendanceSerializer(serializers.ModelSerializer):
    """Read serializer for returning saved Attendance records."""
    student_name = serializers.CharField(source='student.name', read_only=True)
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ['id', 'student', 'student_name', 'date', 'class_name', 'branch', 'year_semester', 'status', 'marked_by', 'marked_by_name']

    def get_marked_by_name(self, obj):
        return obj.marked_by.name if obj.marked_by else None
