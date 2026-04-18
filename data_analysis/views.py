from calendar import monthrange
from datetime import date, datetime, time, timedelta

from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from activity_feed.models import ActivityEvent
from attendance.models import Attendance
from default_activities.models import DefaultActivity
from professor_attendance.models import ProfessorAttendance
from professor_leaves.models import ProfessorLeave
from professors.models import Professor, ProfessorQualification
from subordinate_access.models import SubordinateAccess

from .permissions import DataAnalysisAdminPermission
from .attendance_analytics import (
    build_attendance_analytics_summary,
    build_professor_daily_times,
    build_professor_performance,
    build_student_submission_times,
    build_weekly_trends,
    get_attendance_deadline,
)
from .serializers import (
    AttendanceAnalyticsProfessorDailyTimesSerializer,
    AttendanceAnalyticsStudentSubmissionTimesSerializer,
    AttendanceAnalyticsSummarySerializer,
    AttendanceAnalyticsWeeklyTrendsSerializer,
    ProfessorAttendancePerformanceSummarySerializer,
    ProfessorYearlyAttendanceBulkSerializer,
    ProfessorYearlyAttendanceSummarySerializer,
    TimingAnalysisBulkSerializer,
)


MONTH_LABELS = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
]

DEFAULT_OPENING_TIME = time(8, 0)

PERFORMANCE_COUNT_FIELDS = (
    'on_time_days',
    'late_days',
    'missing_days',
    'expected_working_days',
)


def parse_year_param(request):
    raw_year = (request.query_params.get('year') or '').strip()
    if not raw_year:
        raise ValidationError({'year': ['year is required.']})

    try:
        year = int(raw_year)
    except (TypeError, ValueError) as exc:
        raise ValidationError({'year': ['year must be a valid number.']}) from exc

    if year < 2000 or year > 9999:
        raise ValidationError({'year': ['year must be between 2000 and 9999.']})

    return year


def parse_month_param(request, year):
    raw_month = (request.query_params.get('month') or '').strip()
    if not raw_month:
        return None

    month_parts = raw_month.split('-')
    if len(month_parts) != 2 or len(month_parts[0]) != 4 or len(month_parts[1]) != 2:
        raise ValidationError({'month': ['month must use YYYY-MM format.']})

    try:
        month_year = int(month_parts[0])
        month_number = int(month_parts[1])
        month_start = date(month_year, month_number, 1)
    except (TypeError, ValueError):
        raise ValidationError({'month': ['month must use YYYY-MM format.']})

    if month_start.year != year:
        raise ValidationError({'month': ['month must belong to the selected year.']})

    next_month_start = (
        date(year + 1, 1, 1)
        if month_start.month == 12
        else date(year, month_start.month + 1, 1)
    )

    return {
        'value': raw_month,
        'start_date': month_start,
        'end_date': next_month_start - timedelta(days=1),
        'next_month_start': next_month_start,
    }


def parse_professor_param(request):
    raw_professor_id = (request.query_params.get('professor') or '').strip()
    if not raw_professor_id:
        raise ValidationError({'professor': ['professor is required.']})

    try:
        return int(raw_professor_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError({'professor': ['professor must be a valid number.']}) from exc


def parse_professor_ids_param(request):
    raw_professor_ids = (request.query_params.get('professor_ids') or '').strip()
    if not raw_professor_ids:
        return []

    professor_ids = []
    for raw_professor_id in raw_professor_ids.split(','):
        cleaned_professor_id = raw_professor_id.strip()
        if not cleaned_professor_id:
            continue
        try:
            professor_ids.append(int(cleaned_professor_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {'professor_ids': ['professor_ids must be a comma-separated list of numbers.']}
            ) from exc

    return professor_ids


def build_year_bounds(year):
    return date(year, 1, 1), date(year, 12, 31)


def get_expected_attendance_end_date(year):
    year_start, year_end = build_year_bounds(year)
    today = timezone.localdate()

    if today < year_start:
        return year_start - timedelta(days=1)

    return min(today, year_end)


def build_aware_datetime_bounds(start_date, end_date):
    current_timezone = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(start_date, time.min), current_timezone),
        timezone.make_aware(datetime.combine(end_date, time.min), current_timezone),
    )


def first_specialization_subquery(professor_field):
    return ProfessorQualification.objects.filter(
        professor_id=OuterRef(professor_field),
    ).order_by('id').values('specialization')[:1]


def iterate_date_range(start_date, end_date):
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def build_leave_date_keys(leaves, year_start, year_end):
    leave_date_keys = set()

    for leave in leaves:
        overlap_start = max(leave.start_date, year_start)
        overlap_end = min(leave.end_date, year_end)

        if overlap_end < overlap_start:
            continue

        for current_date in iterate_date_range(overlap_start, overlap_end):
            leave_date_keys.add(current_date.isoformat())

    return leave_date_keys


def get_configured_opening_time(institute):
    return get_attendance_deadline(institute)


def calculate_percentage(numerator, denominator):
    return round((numerator / denominator) * 100) if denominator > 0 else 0


def build_empty_performance_counts():
    return {
        'on_time_days': 0,
        'late_days': 0,
        'missing_days': 0,
        'expected_working_days': 0,
    }


def is_professor_check_record(record):
    return bool(record and record.status is True and record.attendance_time)


def get_computed_attendance_status(record, opening_time):
    if not is_professor_check_record(record):
        return 'missing'

    if record.attendance_time > opening_time:
        return 'late'

    return 'on_time'


def apply_performance_status(performance_counts, status_name):
    if status_name == 'on_time':
        performance_counts['on_time_days'] += 1
    elif status_name == 'late':
        performance_counts['late_days'] += 1
    else:
        performance_counts['missing_days'] += 1


def finalize_performance_counts(performance_counts):
    expected_working_days = performance_counts['expected_working_days']
    performance_counts['on_time_percentage'] = calculate_percentage(
        performance_counts['on_time_days'],
        expected_working_days,
    )
    performance_counts['late_percentage'] = calculate_percentage(
        performance_counts['late_days'],
        expected_working_days,
    )
    performance_counts['missing_percentage'] = calculate_percentage(
        performance_counts['missing_days'],
        expected_working_days,
    )
    return performance_counts


def build_professor_yearly_summary(
    professor,
    year,
    attendance_records,
    accepted_leaves,
    opening_time=None,
):
    resolved_opening_time = opening_time or DEFAULT_OPENING_TIME
    attendance_record_by_date = {
        record.date.isoformat(): record
        for record in attendance_records
    }
    attendance_status_by_date = {
        record.date.isoformat(): bool(record.status)
        for record in attendance_records
    }
    year_start, year_end = build_year_bounds(year)
    expected_end_date = get_expected_attendance_end_date(year)
    leave_date_keys = build_leave_date_keys(accepted_leaves, year_start, year_end)

    months = []
    totals = {
        'present': 0,
        'absent': 0,
        'total': 0,
        'percentage': 0,
        'acceptedLeaves': 0,
        **build_empty_performance_counts(),
    }

    for month in range(1, 13):
        present = 0
        absent = 0
        accepted_leave_days = 0
        performance_counts = build_empty_performance_counts()

        for day in range(1, monthrange(year, month)[1] + 1):
            current_date = date(year, month, day)
            date_key = current_date.isoformat()
            attendance_record = attendance_record_by_date.get(date_key)
            attendance_status = attendance_status_by_date.get(date_key)
            has_accepted_leave = date_key in leave_date_keys

            if attendance_status is True:
                present += 1
            elif attendance_status is False or has_accepted_leave:
                absent += 1

            if has_accepted_leave and attendance_status is not True:
                accepted_leave_days += 1

            if current_date <= expected_end_date and current_date.weekday() != 6:
                if has_accepted_leave and not is_professor_check_record(attendance_record):
                    continue

                performance_counts['expected_working_days'] += 1
                apply_performance_status(
                    performance_counts,
                    get_computed_attendance_status(
                        attendance_record,
                        resolved_opening_time,
                    ),
                )

        total = present + absent
        percentage = round((present / total) * 100) if total > 0 else 0
        finalize_performance_counts(performance_counts)

        month_record = {
            'monthIndex': month - 1,
            'label': MONTH_LABELS[month - 1],
            'present': present,
            'absent': absent,
            'total': total,
            'percentage': percentage,
            'acceptedLeaves': accepted_leave_days,
            **performance_counts,
        }
        months.append(month_record)

        totals['present'] += present
        totals['absent'] += absent
        totals['total'] += total
        totals['acceptedLeaves'] += accepted_leave_days
        for field_name in PERFORMANCE_COUNT_FIELDS:
            totals[field_name] += performance_counts[field_name]

    totals['percentage'] = (
        round((totals['present'] / totals['total']) * 100)
        if totals['total'] > 0
        else 0
    )
    finalize_performance_counts(totals)

    return {
        'professor': professor,
        'year': year,
        'opening_time': resolved_opening_time,
        'totals': totals,
        'months': months,
        'generated_at': timezone.now(),
    }


def build_professor_performance_record(
    professor,
    year,
    attendance_records,
    accepted_leaves,
    opening_time,
):
    yearly_summary = build_professor_yearly_summary(
        professor,
        year,
        attendance_records,
        accepted_leaves,
        opening_time,
    )
    totals = yearly_summary['totals']
    return {
        'professor': professor,
        'on_time_days': totals['on_time_days'],
        'late_days': totals['late_days'],
        'missing_days': totals['missing_days'],
        'expected_working_days': totals['expected_working_days'],
        'on_time_percentage': totals['on_time_percentage'],
        'late_percentage': totals['late_percentage'],
        'missing_percentage': totals['missing_percentage'],
    }


def build_performance_summary(performance_records):
    summary = {
        'professor_count': len(performance_records),
        **build_empty_performance_counts(),
    }

    for record in performance_records:
        for field_name in PERFORMANCE_COUNT_FIELDS:
            summary[field_name] += record[field_name]

    return finalize_performance_counts(summary)


def group_attendance_records_by_professor(attendance_records):
    grouped_records = {}
    for record in attendance_records:
        grouped_records.setdefault(record.professor_id, []).append(record)
    return grouped_records


def group_leaves_by_source_professor(leaves):
    grouped_leaves = {}
    for leave in leaves:
        source_professor_id = getattr(leave.published_professor, 'source_professor_id', None)
        if source_professor_id is None:
            continue
        grouped_leaves.setdefault(source_professor_id, []).append(leave)
    return grouped_leaves


def apply_professor_performance_filters(queryset, request):
    search = (request.query_params.get('search') or '').strip()
    name = (request.query_params.get('name') or '').strip()
    employee_id = (request.query_params.get('employee_id') or '').strip()
    department = (request.query_params.get('department') or '').strip()

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(admin_employement__employee_id__icontains=search)
            | Q(experience__department__icontains=search)
        )

    if name:
        queryset = queryset.filter(name__icontains=name)
    if employee_id:
        queryset = queryset.filter(admin_employement__employee_id__icontains=employee_id)
    if department:
        queryset = queryset.filter(experience__department__icontains=department)

    return queryset


def get_yearly_attendance_professor(institute, professor_id):
    try:
        return (
            Professor.objects
            .filter(institute=institute)
            .select_related('experience', 'admin_employement')
            .get(pk=professor_id)
        )
    except Professor.DoesNotExist as exc:
        raise ValidationError(
            {'professor': ['Professor not found in the authenticated institute.']}
        ) from exc


def get_yearly_professor_attendance_records(institute, professor, year_start, year_end):
    return list(
        ProfessorAttendance.objects
        .filter(
            institute=institute,
            professor=professor,
            date__gte=year_start,
            date__lte=year_end,
        )
        .order_by('date', 'id')
    )


def get_yearly_professor_accepted_leaves(institute, professor, year_start, year_end):
    return list(
        ProfessorLeave.objects
        .select_related('published_professor')
        .filter(
            institute=institute,
            published_professor__source_professor_id=professor.id,
            leaves_status=ProfessorLeave.LeaveStatus.ACCEPTED,
            start_date__lte=year_end,
            end_date__gte=year_start,
        )
        .order_by('start_date', 'id')
    )


def build_professor_yearly_attendance_payload(
    institute,
    professor,
    year,
    *,
    include_attendance_records=False,
):
    year_start, year_end = build_year_bounds(year)
    attendance_records = get_yearly_professor_attendance_records(
        institute,
        professor,
        year_start,
        year_end,
    )
    accepted_leaves = get_yearly_professor_accepted_leaves(
        institute,
        professor,
        year_start,
        year_end,
    )
    opening_time = get_configured_opening_time(institute)

    payload = build_professor_yearly_summary(
        professor,
        year,
        attendance_records,
        accepted_leaves,
        opening_time,
    )

    if include_attendance_records:
        payload.update({
            'attendance_records': attendance_records,
            'attendance_count': len(attendance_records),
        })

    return payload


class TimingAnalysisBulkView(GenericAPIView):
    permission_classes = [DataAnalysisAdminPermission]
    serializer_class = TimingAnalysisBulkSerializer

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        year = parse_year_param(request)
        month_context = parse_month_param(request, year)
        timeline_queryset = ActivityEvent.objects.filter(institute=institute)

        if month_context:
            timeline_start, timeline_end = build_aware_datetime_bounds(
                month_context['start_date'],
                month_context['next_month_start'],
            )
            timeline_queryset = timeline_queryset.filter(
                occurred_at__gte=timeline_start,
                occurred_at__lt=timeline_end,
            )
        else:
            timeline_queryset = timeline_queryset.filter(occurred_at__year=year)

        payload = {
            'year': year,
            'default_activity': (
                DefaultActivity.objects
                .filter(institute=institute)
                .order_by('id')
                .first()
            ),
            'professors': list(
                Professor.objects
                .filter(institute=institute)
                .select_related('experience', 'admin_employement')
                .order_by('id')
            ),
            'subordinates': list(
                SubordinateAccess.objects
                .filter(institute=institute)
                .order_by('id')
            ),
            'timeline': list(
                timeline_queryset
                .order_by('-occurred_at', '-id')
            ),
            'timeline_count': 0,
            'generated_at': timezone.now(),
        }
        payload['timeline_count'] = len(payload['timeline'])

        if month_context:
            professor_attendance = list(
                ProfessorAttendance.objects
                .select_related('professor', 'professor__experience')
                .annotate(
                    primary_specialization=Subquery(
                        first_specialization_subquery('professor_id'),
                    ),
                )
                .filter(
                    institute=institute,
                    date__gte=month_context['start_date'],
                    date__lte=month_context['end_date'],
                )
                .order_by('date', 'id')
            )
            student_attendance = list(
                Attendance.objects
                .select_related('student', 'submission', 'submission__marked_by')
                .filter(
                    student__institute=institute,
                    submission__institute=institute,
                    submission__date__gte=month_context['start_date'],
                    submission__date__lte=month_context['end_date'],
                )
                .order_by('submission__date', 'id')
            )
            payload.update({
                'month': month_context['value'],
                'professor_attendance': professor_attendance,
                'professor_attendance_count': len(professor_attendance),
                'student_attendance': student_attendance,
                'student_attendance_count': len(student_attendance),
            })

        serializer = self.get_serializer(payload)
        return Response(serializer.data)


class ProfessorYearlyAttendanceSummaryView(GenericAPIView):
    permission_classes = [DataAnalysisAdminPermission]
    serializer_class = ProfessorYearlyAttendanceSummarySerializer

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        year = parse_year_param(request)
        professor_id = parse_professor_param(request)
        professor = get_yearly_attendance_professor(institute, professor_id)
        payload = build_professor_yearly_attendance_payload(
            institute,
            professor,
            year,
        )
        serializer = self.get_serializer(payload)
        return Response(serializer.data)


class ProfessorYearlyAttendanceBulkView(GenericAPIView):
    permission_classes = [DataAnalysisAdminPermission]
    serializer_class = ProfessorYearlyAttendanceBulkSerializer

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        year = parse_year_param(request)
        professor_id = parse_professor_param(request)
        professor = get_yearly_attendance_professor(institute, professor_id)
        payload = build_professor_yearly_attendance_payload(
            institute,
            professor,
            year,
            include_attendance_records=True,
        )
        serializer = self.get_serializer(payload)
        return Response(serializer.data)


class AttendanceAnalyticsSummaryView(GenericAPIView):
    permission_classes = [DataAnalysisAdminPermission]
    serializer_class = AttendanceAnalyticsSummarySerializer

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        payload = build_attendance_analytics_summary(institute, request)
        serializer = self.get_serializer(payload)
        return Response(serializer.data)


class AttendanceAnalyticsProfessorDailyTimesView(GenericAPIView):
    permission_classes = [DataAnalysisAdminPermission]
    serializer_class = AttendanceAnalyticsProfessorDailyTimesSerializer

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        payload = build_professor_daily_times(institute, request)
        serializer = self.get_serializer(payload)
        return Response(serializer.data)


class AttendanceAnalyticsStudentSubmissionTimesView(GenericAPIView):
    permission_classes = [DataAnalysisAdminPermission]
    serializer_class = AttendanceAnalyticsStudentSubmissionTimesSerializer

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        payload = build_student_submission_times(institute, request)
        serializer = self.get_serializer(payload)
        return Response(serializer.data)


class AttendanceAnalyticsWeeklyTrendsView(GenericAPIView):
    permission_classes = [DataAnalysisAdminPermission]
    serializer_class = AttendanceAnalyticsWeeklyTrendsSerializer

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        payload = build_weekly_trends(institute, request)
        serializer = self.get_serializer(payload)
        return Response(serializer.data)


class ProfessorAttendancePerformanceSummaryView(GenericAPIView):
    permission_classes = [DataAnalysisAdminPermission]
    serializer_class = ProfessorAttendancePerformanceSummarySerializer

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        has_date_range = bool(
            request.query_params.get('start_date') or request.query_params.get('end_date')
        )

        if has_date_range or not request.query_params.get('year'):
            payload = build_professor_performance(institute, request)
        else:
            year = parse_year_param(request)
            year_start, year_end = build_year_bounds(year)
            payload = build_professor_performance(
                institute,
                request,
                start_date=year_start,
                end_date=year_end,
                year=year,
            )

        serializer = self.get_serializer(payload)
        return Response(serializer.data)
