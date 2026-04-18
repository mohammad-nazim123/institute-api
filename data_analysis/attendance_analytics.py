from collections import defaultdict
from datetime import date, datetime, time, timedelta
from statistics import median

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from attendance.models import AttendanceSubmission
from default_activities.models import DefaultActivity
from professor_attendance.models import ProfessorAttendance
from professor_leaves.models import ProfessorLeave
from professors.models import Professor


DEFAULT_ATTENDANCE_DEADLINE = time(10, 0)
DATE_FORMAT = '%Y-%m-%d'


def parse_date_value(value, field_name):
    normalized_value = str(value or '').strip()
    if not normalized_value:
        return None

    try:
        return datetime.strptime(normalized_value, DATE_FORMAT).date()
    except ValueError as exc:
        raise ValidationError({field_name: ['Date must use YYYY-MM-DD format.']}) from exc


def get_default_date_range():
    today = timezone.localdate()
    return today.replace(day=1), today


def parse_attendance_analytics_date_range(request):
    default_start_date, default_end_date = get_default_date_range()
    start_date = (
        parse_date_value(request.query_params.get('start_date'), 'start_date')
        or default_start_date
    )
    end_date = (
        parse_date_value(request.query_params.get('end_date'), 'end_date')
        or default_end_date
    )

    if start_date > end_date:
        raise ValidationError({'end_date': ['end_date must be on or after start_date.']})

    return start_date, end_date


def parse_time_value(value, fallback=DEFAULT_ATTENDANCE_DEADLINE):
    if isinstance(value, time):
        return value.replace(microsecond=0, tzinfo=None)

    normalized_value = str(value or '').strip()
    if not normalized_value:
        return fallback

    for time_format in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(normalized_value, time_format).time()
        except ValueError:
            continue

    return fallback


def get_attendance_deadline(institute):
    configured_deadline = (
        DefaultActivity.objects
        .filter(institute=institute)
        .order_by('id')
        .values_list('opening_time', flat=True)
        .first()
    )
    if configured_deadline:
        return configured_deadline

    return parse_time_value(
        getattr(settings, 'ATTENDANCE_DEADLINE', None),
        DEFAULT_ATTENDANCE_DEADLINE,
    )


def parse_id_list(raw_value, field_name):
    normalized_value = str(raw_value or '').strip()
    if not normalized_value:
        return []

    ids = []
    for raw_id in normalized_value.split(','):
        cleaned_id = raw_id.strip()
        if not cleaned_id:
            continue
        try:
            ids.append(int(cleaned_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {field_name: [f'{field_name} must be a comma-separated list of numbers.']}
            ) from exc

    return ids


def parse_optional_int(raw_value, field_name):
    normalized_value = str(raw_value or '').strip()
    if not normalized_value:
        return None

    try:
        return int(normalized_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field_name: [f'{field_name} must be a valid number.']}) from exc


def get_professor_department(professor):
    experience = getattr(professor, 'experience', None)
    return getattr(experience, 'department', '') or ''


def get_professor_employee_id(professor):
    employment = getattr(professor, 'admin_employement', None)
    return getattr(employment, 'employee_id', '') or ''


def apply_professor_filters(queryset, request):
    professor_id = parse_optional_int(request.query_params.get('professor_id'), 'professor_id')
    professor_ids = parse_id_list(request.query_params.get('professor_ids'), 'professor_ids')
    legacy_professor_id = parse_optional_int(request.query_params.get('professor'), 'professor')
    department = (
        request.query_params.get('department')
        or request.query_params.get('department_id')
        or ''
    )
    search = str(request.query_params.get('search') or '').strip()
    name = str(request.query_params.get('name') or '').strip()
    employee_id = str(request.query_params.get('employee_id') or '').strip()

    selected_ids = set(professor_ids)
    for selected_id in (professor_id, legacy_professor_id):
        if selected_id is not None:
            selected_ids.add(selected_id)

    if selected_ids:
        queryset = queryset.filter(id__in=selected_ids)

    if department:
        queryset = queryset.filter(experience__department__icontains=str(department).strip())

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

    return queryset


def get_filtered_professors(institute, request):
    queryset = (
        Professor.objects
        .filter(institute=institute)
        .select_related('experience', 'admin_employement')
        .order_by('name', 'id')
    )
    return list(apply_professor_filters(queryset, request))


def iterate_date_range(start_date, end_date):
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def build_aware_datetime(day, clock_time):
    if not day or not clock_time:
        return None

    current_timezone = timezone.get_current_timezone()
    combined_value = datetime.combine(day, clock_time.replace(tzinfo=None))
    return timezone.make_aware(combined_value, current_timezone)


def normalize_datetime(value):
    if not value:
        return None

    if timezone.is_aware(value):
        return timezone.localtime(value)

    current_timezone = timezone.get_current_timezone()
    return timezone.make_aware(value, current_timezone)


def calculate_delay_minutes(professor_check_datetime, student_submission_datetime):
    if not professor_check_datetime or not student_submission_datetime:
        return None

    delay_seconds = (
        professor_check_datetime - student_submission_datetime
    ).total_seconds()
    return round(delay_seconds / 60, 2)


def calculate_average(values):
    clean_values = [value for value in values if value is not None]
    if not clean_values:
        return None
    return round(sum(clean_values) / len(clean_values), 2)


def calculate_median(values):
    clean_values = [value for value in values if value is not None]
    if not clean_values:
        return None
    return round(median(clean_values), 2)


def calculate_percentage(numerator, denominator):
    return round((numerator / denominator) * 100) if denominator > 0 else 0


def is_expected_working_day(day):
    return day.weekday() != 6


def is_professor_check_record(record):
    return bool(record and record.status is True and record.attendance_time)


def get_professor_attendance_status(record, deadline):
    if not is_professor_check_record(record):
        return 'missing'
    if record.attendance_time > deadline:
        return 'late'
    return 'on_time'


def build_empty_status_counts():
    return {
        'on_time_days': 0,
        'late_days': 0,
        'missing_days': 0,
        'expected_working_days': 0,
    }


def apply_status_count(counts, status_name):
    if status_name == 'on_time':
        counts['on_time_days'] += 1
    elif status_name == 'late':
        counts['late_days'] += 1
    else:
        counts['missing_days'] += 1


def finalize_status_counts(counts):
    expected_working_days = counts['expected_working_days']
    counts['on_time_percentage'] = calculate_percentage(
        counts['on_time_days'],
        expected_working_days,
    )
    counts['late_percentage'] = calculate_percentage(
        counts['late_days'],
        expected_working_days,
    )
    counts['missing_percentage'] = calculate_percentage(
        counts['missing_days'],
        expected_working_days,
    )
    return counts


def group_records_by_professor_and_date(records):
    grouped = {}
    for record in records:
        grouped[(record.professor_id, record.date)] = record
    return grouped


def group_submissions_by_professor_and_date(submissions):
    grouped = defaultdict(list)
    for submission in submissions:
        if not submission.marked_by_id:
            continue
        grouped[(submission.marked_by_id, submission.date)].append(submission)
    return grouped


def group_leaves_by_professor(leaves):
    grouped = defaultdict(list)
    for leave in leaves:
        source_professor_id = getattr(leave.published_professor, 'source_professor_id', None)
        if source_professor_id is None:
            continue
        grouped[source_professor_id].append(leave)
    return grouped


def build_leave_date_set(leaves, start_date, end_date):
    leave_dates = set()
    for leave in leaves:
        overlap_start = max(leave.start_date, start_date)
        overlap_end = min(leave.end_date, end_date)
        if overlap_end < overlap_start:
            continue
        for current_date in iterate_date_range(overlap_start, overlap_end):
            leave_dates.add(current_date)
    return leave_dates


def build_submission_delay_record(submission, professor, attendance_record):
    professor_check_datetime = build_aware_datetime(
        submission.date,
        attendance_record.attendance_time if is_professor_check_record(attendance_record) else None,
    )
    student_submission_datetime = normalize_datetime(submission.submitted_at)
    delay_minutes = calculate_delay_minutes(
        professor_check_datetime,
        student_submission_datetime,
    )
    student_count = int(getattr(submission, 'student_count', 0) or 0)
    present_count = int(getattr(submission, 'present_count', 0) or 0)

    return {
        'id': submission.id,
        'professor_id': professor.id,
        'professor_name': professor.name,
        'department': get_professor_department(professor),
        'date': submission.date,
        'class_name': submission.class_name,
        'branch': submission.branch,
        'year_semester': submission.year_semester,
        'student_count': student_count,
        'present_count': present_count,
        'absent_count': max(student_count - present_count, 0),
        'student_submission_time': student_submission_datetime,
        'student_submission_clock_time': submission.attendance_time,
        'professor_check_time': (
            attendance_record.attendance_time
            if is_professor_check_record(attendance_record)
            else None
        ),
        'delay_minutes': delay_minutes,
        'status': get_professor_attendance_status(attendance_record, time.max),
    }


def build_attendance_analytics_dataset(institute, request, start_date=None, end_date=None):
    resolved_start_date = start_date
    resolved_end_date = end_date
    if resolved_start_date is None or resolved_end_date is None:
        resolved_start_date, resolved_end_date = parse_attendance_analytics_date_range(request)

    today = timezone.localdate()
    effective_end_date = min(resolved_end_date, today)
    deadline = get_attendance_deadline(institute)
    professors = get_filtered_professors(institute, request)
    professor_ids = [professor.id for professor in professors]

    attendance_records_by_key = {}
    submissions_by_key = defaultdict(list)
    leaves_by_professor = defaultdict(list)

    if professor_ids:
        attendance_records_by_key = group_records_by_professor_and_date(
            ProfessorAttendance.objects
            .filter(
                institute=institute,
                professor_id__in=professor_ids,
                date__gte=resolved_start_date,
                date__lte=resolved_end_date,
            )
            .select_related('professor')
            .order_by('professor_id', 'date')
        )
        submissions_by_key = group_submissions_by_professor_and_date(
            AttendanceSubmission.objects
            .filter(
                institute=institute,
                marked_by_id__in=professor_ids,
                date__gte=resolved_start_date,
                date__lte=resolved_end_date,
            )
            .select_related('marked_by', 'marked_by__experience')
            .annotate(
                student_count=Count('attendance_records', distinct=True),
                present_count=Count(
                    'attendance_records',
                    filter=Q(attendance_records__status=True),
                    distinct=True,
                ),
            )
            .order_by('date', 'marked_by_id', 'class_name', 'branch', 'year_semester', 'id')
        )
        leaves_by_professor = group_leaves_by_professor(
            ProfessorLeave.objects
            .select_related('published_professor')
            .filter(
                institute=institute,
                published_professor__source_professor_id__in=professor_ids,
                leaves_status=ProfessorLeave.LeaveStatus.ACCEPTED,
                start_date__lte=resolved_end_date,
                end_date__gte=resolved_start_date,
            )
            .order_by('published_professor__source_professor_id', 'start_date', 'id')
        )

    daily_rows = []
    submission_rows = []
    performance_rows = []
    summary_counts = build_empty_status_counts()
    all_delay_values = []

    for professor in professors:
        professor_counts = build_empty_status_counts()
        professor_delay_values = []
        professor_leaves = leaves_by_professor.get(professor.id, [])
        leave_dates = build_leave_date_set(
            professor_leaves,
            resolved_start_date,
            effective_end_date,
        )

        if resolved_start_date <= effective_end_date:
            for current_date in iterate_date_range(resolved_start_date, effective_end_date):
                if not is_expected_working_day(current_date):
                    continue

                attendance_record = attendance_records_by_key.get((professor.id, current_date))
                if current_date in leave_dates and not is_professor_check_record(attendance_record):
                    continue

                status_name = get_professor_attendance_status(attendance_record, deadline)
                professor_counts['expected_working_days'] += 1
                summary_counts['expected_working_days'] += 1
                apply_status_count(professor_counts, status_name)
                apply_status_count(summary_counts, status_name)

                submissions = submissions_by_key.get((professor.id, current_date), [])
                daily_delay_values = []
                for submission in submissions:
                    submission_record = build_submission_delay_record(
                        submission,
                        professor,
                        attendance_record,
                    )
                    if submission_record['delay_minutes'] is not None:
                        daily_delay_values.append(submission_record['delay_minutes'])

                daily_average_delay = calculate_average(daily_delay_values)
                daily_rows.append({
                    'professor_id': professor.id,
                    'professor_name': professor.name,
                    'department': get_professor_department(professor),
                    'date': current_date,
                    'professor_check_time': (
                        attendance_record.attendance_time
                        if is_professor_check_record(attendance_record)
                        else None
                    ),
                    'student_submission_count': len(submissions),
                    'delay_minutes': daily_average_delay,
                    'average_delay_minutes': daily_average_delay,
                    'median_delay_minutes': calculate_median(daily_delay_values),
                    'status': status_name,
                })

        for (submission_professor_id, submission_date), submissions in submissions_by_key.items():
            if submission_professor_id != professor.id:
                continue
            if not resolved_start_date <= submission_date <= resolved_end_date:
                continue
            attendance_record = attendance_records_by_key.get((professor.id, submission_date))
            status_name = get_professor_attendance_status(attendance_record, deadline)
            for submission in submissions:
                submission_record = build_submission_delay_record(
                    submission,
                    professor,
                    attendance_record,
                )
                submission_record['status'] = status_name
                submission_rows.append(submission_record)
                if submission_record['delay_minutes'] is not None:
                    professor_delay_values.append(submission_record['delay_minutes'])
                    all_delay_values.append(submission_record['delay_minutes'])

        finalize_status_counts(professor_counts)
        performance_rows.append({
            'professor': professor,
            'professor_id': professor.id,
            'professor_name': professor.name,
            'department': get_professor_department(professor),
            'employee_id': get_professor_employee_id(professor),
            'average_delay_minutes': calculate_average(professor_delay_values),
            'median_delay_minutes': calculate_median(professor_delay_values),
            **professor_counts,
        })

    finalize_status_counts(summary_counts)
    summary = {
        'total_professors': len(professors),
        'professor_count': len(professors),
        'missing_attendance_days': summary_counts['missing_days'],
        'average_delay_minutes': calculate_average(all_delay_values),
        'median_delay_minutes': calculate_median(all_delay_values),
        **summary_counts,
    }

    return {
        'start_date': resolved_start_date,
        'end_date': resolved_end_date,
        'effective_end_date': effective_end_date,
        'deadline': deadline,
        'opening_time': deadline,
        'professors': professors,
        'summary': summary,
        'daily_rows': sorted(
            daily_rows,
            key=lambda row: (row['date'], row['professor_name'].lower(), row['professor_id']),
        ),
        'submission_rows': sorted(
            submission_rows,
            key=lambda row: (
                row['date'],
                row['professor_name'].lower(),
                row.get('class_name') or '',
                row.get('branch') or '',
                row.get('id') or 0,
            ),
        ),
        'performance_rows': performance_rows,
        'generated_at': timezone.now(),
    }


def build_attendance_analytics_summary(institute, request):
    dataset = build_attendance_analytics_dataset(institute, request)
    return {
        'start_date': dataset['start_date'],
        'end_date': dataset['end_date'],
        'effective_end_date': dataset['effective_end_date'],
        'deadline': dataset['deadline'],
        'generated_at': dataset['generated_at'],
        **dataset['summary'],
    }


def build_professor_daily_times(institute, request):
    dataset = build_attendance_analytics_dataset(institute, request)
    return {
        'start_date': dataset['start_date'],
        'end_date': dataset['end_date'],
        'effective_end_date': dataset['effective_end_date'],
        'deadline': dataset['deadline'],
        'results': dataset['daily_rows'],
        'count': len(dataset['daily_rows']),
        'generated_at': dataset['generated_at'],
    }


def build_student_submission_times(institute, request):
    dataset = build_attendance_analytics_dataset(institute, request)
    return {
        'start_date': dataset['start_date'],
        'end_date': dataset['end_date'],
        'effective_end_date': dataset['effective_end_date'],
        'deadline': dataset['deadline'],
        'results': dataset['submission_rows'],
        'count': len(dataset['submission_rows']),
        'generated_at': dataset['generated_at'],
    }


def get_week_start(day):
    return day - timedelta(days=day.weekday())


def format_week_label(week_start, week_end):
    return (
        f'{week_start.strftime("%d %b")} - '
        f'{week_end.strftime("%d %b %Y")}'
    )


def build_weekly_trends(institute, request):
    dataset = build_attendance_analytics_dataset(institute, request)
    start_date = dataset['start_date']
    effective_end_date = dataset['effective_end_date']

    if start_date > effective_end_date:
        return {
            'start_date': dataset['start_date'],
            'end_date': dataset['end_date'],
            'effective_end_date': dataset['effective_end_date'],
            'deadline': dataset['deadline'],
            'results': [],
            'count': 0,
            'generated_at': dataset['generated_at'],
        }

    week_buckets = {}
    current_week_start = get_week_start(start_date)
    while current_week_start <= effective_end_date:
        week_start = max(current_week_start, start_date)
        week_end = min(current_week_start + timedelta(days=6), effective_end_date)
        week_buckets[current_week_start] = {
            'week_label': format_week_label(week_start, week_end),
            'week_start': week_start,
            'week_end': week_end,
            'delay_values': [],
            'on_time_days': 0,
            'late_days': 0,
            'missing_count': 0,
            'expected_working_days': 0,
        }
        current_week_start += timedelta(days=7)

    for row in dataset['daily_rows']:
        week_key = get_week_start(row['date'])
        bucket = week_buckets.get(week_key)
        if not bucket:
            continue
        bucket['expected_working_days'] += 1
        if row['status'] == 'on_time':
            bucket['on_time_days'] += 1
        elif row['status'] == 'late':
            bucket['late_days'] += 1
        else:
            bucket['missing_count'] += 1

    for row in dataset['submission_rows']:
        if row['delay_minutes'] is None:
            continue
        week_key = get_week_start(row['date'])
        bucket = week_buckets.get(week_key)
        if not bucket:
            continue
        bucket['delay_values'].append(row['delay_minutes'])

    results = []
    for week_key in sorted(week_buckets):
        bucket = week_buckets[week_key]
        expected_working_days = bucket['expected_working_days']
        results.append({
            'week_label': bucket['week_label'],
            'week_start': bucket['week_start'],
            'week_end': bucket['week_end'],
            'average_delay_minutes': calculate_average(bucket['delay_values']),
            'on_time_percentage': calculate_percentage(
                bucket['on_time_days'],
                expected_working_days,
            ),
            'missing_count': bucket['missing_count'],
            'expected_working_days': expected_working_days,
            'late_days': bucket['late_days'],
            'on_time_days': bucket['on_time_days'],
        })

    return {
        'start_date': dataset['start_date'],
        'end_date': dataset['end_date'],
        'effective_end_date': dataset['effective_end_date'],
        'deadline': dataset['deadline'],
        'results': results,
        'count': len(results),
        'generated_at': dataset['generated_at'],
    }


def build_professor_performance(institute, request, start_date=None, end_date=None, year=None):
    dataset = build_attendance_analytics_dataset(
        institute,
        request,
        start_date=start_date,
        end_date=end_date,
    )
    payload = {
        'start_date': dataset['start_date'],
        'end_date': dataset['end_date'],
        'effective_end_date': dataset['effective_end_date'],
        'opening_time': dataset['opening_time'],
        'deadline': dataset['deadline'],
        'summary': dataset['summary'],
        'professors': dataset['performance_rows'],
        'generated_at': dataset['generated_at'],
    }
    if year is not None:
        payload['year'] = year
    return payload
