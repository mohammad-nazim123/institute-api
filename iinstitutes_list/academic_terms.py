import re

from django.db.models import Q


ACADEMIC_TERMS_TYPE_SEMESTER = 'semester'
ACADEMIC_TERMS_TYPE_YEAR = 'year'

ACADEMIC_TERMS_TYPE_CHOICES = [
    (ACADEMIC_TERMS_TYPE_SEMESTER, 'Semester Wise'),
    (ACADEMIC_TERMS_TYPE_YEAR, 'Year Wise'),
]

ACADEMIC_TERMS_TOTAL_BY_TYPE = {
    ACADEMIC_TERMS_TYPE_SEMESTER: 8,
    ACADEMIC_TERMS_TYPE_YEAR: 4,
}

ACADEMIC_TERM_SUFFIX_BY_TYPE = {
    ACADEMIC_TERMS_TYPE_SEMESTER: 'Semester',
    ACADEMIC_TERMS_TYPE_YEAR: 'Year',
}

ACADEMIC_TERM_NUMBER_RE = re.compile(r'(\d+)', re.IGNORECASE)


def normalize_academic_terms_type(value):
    normalized = str(value or '').strip().lower()
    if normalized in {ACADEMIC_TERMS_TYPE_YEAR, 'year wise', 'yearwise'}:
        return ACADEMIC_TERMS_TYPE_YEAR
    if normalized in {ACADEMIC_TERMS_TYPE_SEMESTER, 'semester wise', 'semesterwise'}:
        return ACADEMIC_TERMS_TYPE_SEMESTER
    return ACADEMIC_TERMS_TYPE_SEMESTER


def ordinal_label(number):
    number = int(number)
    if 10 <= (number % 100) <= 20:
        suffix = 'th'
    else:
        suffix = {
            1: 'st',
            2: 'nd',
            3: 'rd',
        }.get(number % 10, 'th')
    return f'{number}{suffix}'


def render_academic_term(index, academic_terms_type):
    normalized_type = normalize_academic_terms_type(academic_terms_type)
    suffix = ACADEMIC_TERM_SUFFIX_BY_TYPE[normalized_type]
    return f'{ordinal_label(index)} {suffix}'


def extract_academic_term_index(value):
    text = str(value or '').strip()
    if not text:
        return None

    match = ACADEMIC_TERM_NUMBER_RE.search(text)
    if match is None:
        return None
    return int(match.group(1))


def canonicalize_academic_term_value(value, academic_terms_type):
    text = str(value or '').strip()
    if not text:
        return text

    index = extract_academic_term_index(text)
    if index is None:
        return text

    return render_academic_term(index, academic_terms_type)


def canonicalize_institute_academic_term(institute, value):
    academic_terms_type = getattr(institute, 'academic_terms_type', None)
    return canonicalize_academic_term_value(value, academic_terms_type)


def build_academic_term_aliases(value, academic_terms_type):
    text = str(value or '').strip()
    if not text:
        return []

    index = extract_academic_term_index(text)
    if index is None:
        return [text]

    normalized_type = normalize_academic_terms_type(academic_terms_type)
    suffix = ACADEMIC_TERM_SUFFIX_BY_TYPE[normalized_type]
    ordinal = ordinal_label(index)
    aliases = [
        f'{ordinal} {suffix}',
        f'{suffix} {ordinal}',
        f'{index} {suffix}',
        f'{suffix} {index}',
    ]

    unique_aliases = []
    seen = set()
    for alias in aliases:
        lowered = alias.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_aliases.append(alias)
    return unique_aliases


def build_academic_term_query(field_name, value, institute_or_type=None):
    academic_terms_type = getattr(institute_or_type, 'academic_terms_type', institute_or_type)
    aliases = build_academic_term_aliases(value, academic_terms_type)
    if not aliases:
        return None

    query = Q()
    for alias in aliases:
        query |= Q(**{f'{field_name}__iexact': alias})
    return query


def filter_queryset_by_academic_term(queryset, field_name, value, institute_or_type=None):
    query = build_academic_term_query(field_name, value, institute_or_type=institute_or_type)
    if query is None:
        return queryset
    return queryset.filter(query)


def build_academic_terms_for_type(academic_terms_type):
    normalized_type = normalize_academic_terms_type(academic_terms_type)
    total = ACADEMIC_TERMS_TOTAL_BY_TYPE[normalized_type]
    return [
        render_academic_term(index, normalized_type)
        for index in range(1, total + 1)
    ]


def get_academic_terms_for_institute(institute):
    return build_academic_terms_for_type(getattr(institute, 'academic_terms_type', None))


def _bulk_sync_term_values(queryset, field_name, academic_terms_type):
    objects_to_update = []

    for obj in queryset:
        current_value = getattr(obj, field_name, '')
        normalized_value = canonicalize_academic_term_value(current_value, academic_terms_type)
        if normalized_value == current_value:
            continue
        setattr(obj, field_name, normalized_value)
        objects_to_update.append(obj)

    if not objects_to_update:
        return 0

    queryset.model.objects.bulk_update(objects_to_update, [field_name])
    return len(objects_to_update)


def sync_institute_academic_terms(institute):
    academic_terms_type = normalize_academic_terms_type(getattr(institute, 'academic_terms_type', None))
    summary = {}

    from attendance.models import Attendance
    from published_exam_result.models import PublishedExamResult
    from published_schedules.models import PublishedExamSchedule, PublishedWeeklySchedule
    from published_student.models import PublishedStudent
    from set_exam_data.models import ExamData
    from students.models import StudentCourseAssignment
    from syllabus.models import AcademicTerms
    from weekly_exam_schedule.models import ExamScheduleData, WeeklyScheduleData

    summary['syllabus_terms'] = _bulk_sync_term_values(
        AcademicTerms.objects.filter(branch__course__institute=institute).only('id', 'name'),
        'name',
        academic_terms_type,
    )
    summary['student_course_assignments'] = _bulk_sync_term_values(
        StudentCourseAssignment.objects.filter(student__institute=institute).only('id', 'academic_term'),
        'academic_term',
        academic_terms_type,
    )
    summary['attendance'] = _bulk_sync_term_values(
        Attendance.objects.filter(student__institute=institute).only('id', 'year_semester'),
        'year_semester',
        academic_terms_type,
    )
    summary['exam_data'] = _bulk_sync_term_values(
        ExamData.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        academic_terms_type,
    )
    summary['weekly_schedule_data'] = _bulk_sync_term_values(
        WeeklyScheduleData.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        academic_terms_type,
    )
    summary['exam_schedule_data'] = _bulk_sync_term_values(
        ExamScheduleData.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        academic_terms_type,
    )
    summary['published_weekly_schedules'] = _bulk_sync_term_values(
        PublishedWeeklySchedule.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        academic_terms_type,
    )
    summary['published_exam_schedules'] = _bulk_sync_term_values(
        PublishedExamSchedule.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        academic_terms_type,
    )

    published_students_to_update = []
    for snapshot in PublishedStudent.objects.filter(institute=institute).only('id', 'student_data'):
        student_data = dict(snapshot.student_data or {})
        course_assignment = dict(student_data.get('course_assignment') or {})
        current_value = course_assignment.get('academic_term', '')
        normalized_value = canonicalize_academic_term_value(current_value, academic_terms_type)
        if normalized_value == current_value:
            continue
        course_assignment['academic_term'] = normalized_value
        student_data['course_assignment'] = course_assignment
        snapshot.student_data = student_data
        published_students_to_update.append(snapshot)
    if published_students_to_update:
        PublishedStudent.objects.bulk_update(published_students_to_update, ['student_data'])
    summary['published_students'] = len(published_students_to_update)

    published_exam_results_to_update = []
    for snapshot in PublishedExamResult.objects.filter(institute=institute).only('id', 'exam_results'):
        exam_results = []
        changed = False
        for item in list(snapshot.exam_results or []):
            updated_item = dict(item)
            current_value = updated_item.get('academic_term', '')
            normalized_value = canonicalize_academic_term_value(current_value, academic_terms_type)
            if normalized_value != current_value:
                updated_item['academic_term'] = normalized_value
                changed = True
            exam_results.append(updated_item)

        if not changed:
            continue

        snapshot.exam_results = exam_results
        published_exam_results_to_update.append(snapshot)
    if published_exam_results_to_update:
        PublishedExamResult.objects.bulk_update(published_exam_results_to_update, ['exam_results'])
    summary['published_exam_results'] = len(published_exam_results_to_update)

    summary['total_updates'] = sum(summary.values())
    return summary
