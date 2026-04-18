from rest_framework import serializers

from activity_feed.serializers import ActivityEventSerializer
from attendance.serializers import AttendanceSerializer
from default_activities.serializers import DefaultActivitySerializer
from professor_attendance.models import ProfessorAttendance
from professor_attendance.serializers import ProfessorAttendanceSerializer
from professors.models import Professor
from subordinate_access.models import SubordinateAccess


class DataAnalysisProfessorSerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    experience = serializers.SerializerMethodField()
    admin_employement = serializers.SerializerMethodField()

    class Meta:
        model = Professor
        fields = [
            'id',
            'name',
            'department',
            'employee_id',
            'experience',
            'admin_employement',
        ]

    def get_department(self, obj):
        experience = getattr(obj, 'experience', None)
        return getattr(experience, 'department', '')

    def get_employee_id(self, obj):
        employment = getattr(obj, 'admin_employement', None)
        return getattr(employment, 'employee_id', '')

    def get_experience(self, obj):
        department = self.get_department(obj)
        return {'department': department} if department else {}

    def get_admin_employement(self, obj):
        employee_id = self.get_employee_id(obj)
        return {'employee_id': employee_id} if employee_id else {}


class DataAnalysisSubordinateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubordinateAccess
        fields = [
            'id',
            'post',
            'name',
            'access_control',
            'is_active',
        ]


class TimingAnalysisBulkSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.CharField(required=False, allow_blank=True)
    default_activity = serializers.SerializerMethodField()
    professors = DataAnalysisProfessorSerializer(many=True)
    subordinates = DataAnalysisSubordinateSerializer(many=True)
    timeline = ActivityEventSerializer(many=True)
    timeline_count = serializers.IntegerField()
    professor_attendance = ProfessorAttendanceSerializer(many=True, required=False)
    professor_attendance_count = serializers.IntegerField(required=False)
    student_attendance = AttendanceSerializer(many=True, required=False)
    student_attendance_count = serializers.IntegerField(required=False)
    generated_at = serializers.DateTimeField()

    def get_default_activity(self, obj):
        default_activity = obj.get('default_activity')
        if default_activity is None:
            return None
        return DefaultActivitySerializer(default_activity).data


class ProfessorYearlyAttendanceSummarySerializer(serializers.Serializer):
    professor = DataAnalysisProfessorSerializer()
    year = serializers.IntegerField()
    opening_time = serializers.TimeField(required=False)
    totals = serializers.DictField()
    months = serializers.ListField()
    generated_at = serializers.DateTimeField()


class DataAnalysisProfessorAttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessorAttendance
        fields = [
            'id',
            'professor',
            'date',
            'status',
            'attendance_time',
        ]


class ProfessorYearlyAttendanceBulkSerializer(ProfessorYearlyAttendanceSummarySerializer):
    attendance_records = DataAnalysisProfessorAttendanceRecordSerializer(many=True)
    attendance_count = serializers.IntegerField()


class ProfessorAttendancePerformanceRecordSerializer(serializers.Serializer):
    professor = DataAnalysisProfessorSerializer()
    professor_id = serializers.IntegerField(required=False)
    professor_name = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(required=False, allow_blank=True)
    employee_id = serializers.CharField(required=False, allow_blank=True)
    average_delay_minutes = serializers.FloatField(required=False, allow_null=True)
    median_delay_minutes = serializers.FloatField(required=False, allow_null=True)
    on_time_days = serializers.IntegerField()
    late_days = serializers.IntegerField()
    missing_days = serializers.IntegerField()
    expected_working_days = serializers.IntegerField()
    on_time_percentage = serializers.IntegerField()
    late_percentage = serializers.IntegerField()
    missing_percentage = serializers.IntegerField()


class ProfessorAttendancePerformanceSummarySerializer(serializers.Serializer):
    year = serializers.IntegerField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    effective_end_date = serializers.DateField(required=False)
    opening_time = serializers.TimeField()
    deadline = serializers.TimeField(required=False)
    summary = serializers.DictField()
    professors = ProfessorAttendancePerformanceRecordSerializer(many=True)
    generated_at = serializers.DateTimeField()


class AttendanceAnalyticsSummarySerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    effective_end_date = serializers.DateField()
    deadline = serializers.TimeField()
    total_professors = serializers.IntegerField()
    professor_count = serializers.IntegerField()
    on_time_days = serializers.IntegerField()
    late_days = serializers.IntegerField()
    missing_days = serializers.IntegerField()
    expected_working_days = serializers.IntegerField()
    on_time_percentage = serializers.IntegerField()
    late_percentage = serializers.IntegerField()
    missing_percentage = serializers.IntegerField()
    missing_attendance_days = serializers.IntegerField()
    average_delay_minutes = serializers.FloatField(allow_null=True)
    median_delay_minutes = serializers.FloatField(allow_null=True)
    generated_at = serializers.DateTimeField()


class AttendanceAnalyticsProfessorDailyTimeRecordSerializer(serializers.Serializer):
    professor_id = serializers.IntegerField()
    professor_name = serializers.CharField()
    department = serializers.CharField(allow_blank=True)
    date = serializers.DateField()
    professor_check_time = serializers.TimeField(allow_null=True)
    student_submission_count = serializers.IntegerField()
    delay_minutes = serializers.FloatField(allow_null=True)
    average_delay_minutes = serializers.FloatField(allow_null=True)
    median_delay_minutes = serializers.FloatField(allow_null=True)
    status = serializers.CharField()


class AttendanceAnalyticsProfessorDailyTimesSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    effective_end_date = serializers.DateField()
    deadline = serializers.TimeField()
    results = AttendanceAnalyticsProfessorDailyTimeRecordSerializer(many=True)
    count = serializers.IntegerField()
    generated_at = serializers.DateTimeField()


class AttendanceAnalyticsStudentSubmissionTimeRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    professor_id = serializers.IntegerField()
    professor_name = serializers.CharField()
    department = serializers.CharField(allow_blank=True)
    date = serializers.DateField()
    class_name = serializers.CharField(allow_blank=True)
    branch = serializers.CharField(allow_blank=True)
    year_semester = serializers.CharField(allow_blank=True)
    student_count = serializers.IntegerField()
    present_count = serializers.IntegerField()
    absent_count = serializers.IntegerField()
    student_submission_time = serializers.DateTimeField(allow_null=True)
    student_submission_clock_time = serializers.TimeField(allow_null=True)
    professor_check_time = serializers.TimeField(allow_null=True)
    delay_minutes = serializers.FloatField(allow_null=True)
    status = serializers.CharField()


class AttendanceAnalyticsStudentSubmissionTimesSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    effective_end_date = serializers.DateField()
    deadline = serializers.TimeField()
    results = AttendanceAnalyticsStudentSubmissionTimeRecordSerializer(many=True)
    count = serializers.IntegerField()
    generated_at = serializers.DateTimeField()


class AttendanceAnalyticsWeeklyTrendRecordSerializer(serializers.Serializer):
    week_label = serializers.CharField()
    week_start = serializers.DateField()
    week_end = serializers.DateField()
    average_delay_minutes = serializers.FloatField(allow_null=True)
    on_time_percentage = serializers.IntegerField()
    missing_count = serializers.IntegerField()
    expected_working_days = serializers.IntegerField()
    late_days = serializers.IntegerField()
    on_time_days = serializers.IntegerField()


class AttendanceAnalyticsWeeklyTrendsSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    effective_end_date = serializers.DateField()
    deadline = serializers.TimeField()
    results = AttendanceAnalyticsWeeklyTrendRecordSerializer(many=True)
    count = serializers.IntegerField()
    generated_at = serializers.DateTimeField()
