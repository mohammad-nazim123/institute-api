from rest_framework import serializers
from professors.models import Professor
from students.models import Student
from .models import Attendance, AttendanceSubmission


class StudentSerializer(serializers.ModelSerializer):
    """Minimal student representation for the GET /api/students/ endpoint."""

    class Meta:
        model = Student
        fields = ['id', 'name', 'gender', 'category']


class StudentAttendanceRecordSerializer(serializers.ModelSerializer):
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'id',
            'date',
            'class_name',
            'branch',
            'year_semester',
            'status',
            'marked_by',
            'marked_by_name',
            'attendance_time',
            'submitted_at',
        ]

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
    # Kept optional for older clients, but new bulk requests send shared
    # metadata once on MarkAttendanceSerializer.
    class_name = serializers.CharField(max_length=50, default='', required=False)
    branch = serializers.CharField(max_length=30, default='', required=False)
    year_semester = serializers.CharField(max_length=20, default='', required=False)


class MarkAttendanceSerializer(serializers.Serializer):
    """Top-level serializer for POST /api/attendance/mark/"""
    date = serializers.DateField()
    class_name = serializers.CharField(max_length=50, default='', required=False)
    branch = serializers.CharField(max_length=30, default='', required=False)
    year_semester = serializers.CharField(max_length=20, default='', required=False)
    attendance = AttendanceRecordSerializer(many=True)

    def validate_attendance(self, value):
        if not value:
            raise serializers.ValidationError("Attendance list must not be empty.")
        return value


class AttendanceSerializer(serializers.ModelSerializer):
    """Read serializer for returning saved Attendance records."""
    date = serializers.DateField(required=False)
    class_name = serializers.CharField(max_length=50, default='', required=False)
    branch = serializers.CharField(max_length=30, default='', required=False)
    year_semester = serializers.CharField(max_length=20, default='', required=False)
    attendance_time = serializers.TimeField(read_only=True)
    marked_by = serializers.PrimaryKeyRelatedField(
        queryset=Professor.objects.all(),
        required=False,
        allow_null=True,
    )
    submitted_at = serializers.DateTimeField(read_only=True)
    student_name = serializers.CharField(source='student.name', read_only=True)
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'id',
            'student',
            'student_name',
            'date',
            'class_name',
            'branch',
            'year_semester',
            'status',
            'marked_by',
            'marked_by_name',
            'attendance_time',
            'submitted_at',
        ]
        read_only_fields = ['attendance_time', 'submitted_at']
        validators = []

    def get_marked_by_name(self, obj):
        return obj.marked_by.name if obj.marked_by else None

    def _normalize_year_semester(self, value):
        institute = self.context.get('institute')
        if not institute:
            return str(value or '').strip()

        from iinstitutes_list.academic_terms import canonicalize_institute_academic_term

        return canonicalize_institute_academic_term(institute, value or '')

    def _get_submission_metadata(self, attrs):
        instance = self.instance
        submitted_at = attrs.pop('submitted_at', getattr(instance, 'submitted_at', timezone_now()))
        return {
            'date': attrs.pop('date', getattr(instance, 'date', None)),
            'class_name': attrs.pop('class_name', getattr(instance, 'class_name', '')),
            'branch': attrs.pop('branch', getattr(instance, 'branch', '')),
            'year_semester': attrs.pop('year_semester', getattr(instance, 'year_semester', '')),
            'marked_by': attrs.pop('marked_by', getattr(instance, 'marked_by', None)),
            'submitted_at': submitted_at,
            'attendance_time': attrs.pop(
                'attendance_time',
                AttendanceSubmission.derive_attendance_time(submitted_at),
            ),
        }

    def _get_or_update_submission(self, metadata):
        institute = self.context.get('institute')
        if not institute:
            raise serializers.ValidationError('Institute context is required.')

        date = metadata.get('date')
        if not date:
            raise serializers.ValidationError({'date': 'This field is required.'})

        marked_by = metadata.get('marked_by') or self.context.get('marked_by')
        year_semester = self._normalize_year_semester(metadata.get('year_semester', ''))
        submitted_at = metadata.get('submitted_at') or timezone_now()
        attendance_time = (
            metadata.get('attendance_time')
            or AttendanceSubmission.derive_attendance_time(submitted_at)
        )

        submission, _created = AttendanceSubmission.objects.update_or_create(
            institute=institute,
            date=date,
            class_name=metadata.get('class_name', '') or '',
            branch=metadata.get('branch', '') or '',
            year_semester=year_semester,
            defaults={
                'marked_by': marked_by,
                'submitted_at': submitted_at,
                'attendance_time': attendance_time,
            },
        )
        return submission

    def validate_student(self, student):
        institute = self.context.get('institute')
        if institute and student.institute_id != institute.id:
            raise serializers.ValidationError(
                'Student not found in the authenticated institute.'
            )
        return student

    def validate_marked_by(self, marked_by):
        institute = self.context.get('institute')
        if institute and marked_by and marked_by.institute_id != institute.id:
            raise serializers.ValidationError(
                'Professor not found in the authenticated institute.'
            )
        return marked_by

    def validate(self, attrs):
        student = attrs.get('student') or getattr(self.instance, 'student', None)
        date = attrs.get('date') or getattr(self.instance, 'date', None)

        if student and date:
            queryset = Attendance.objects.filter(
                student=student,
                submission__date=date,
            )
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    'Attendance already exists for this student on this date.'
                )

        return attrs

    def create(self, validated_data):
        metadata = self._get_submission_metadata(validated_data)
        validated_data['submission'] = self._get_or_update_submission(metadata)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        metadata = self._get_submission_metadata(validated_data)
        instance.submission = self._get_or_update_submission(metadata)
        instance.status = validated_data.get('status', instance.status)
        instance.student = validated_data.get('student', instance.student)
        instance.save(update_fields=['student', 'submission', 'status'])
        return instance


def timezone_now():
    from django.utils import timezone

    return timezone.now()
