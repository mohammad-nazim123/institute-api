import re

from django.apps import apps
from django.db.models import Q


ACADEMIC_TERM_NUMBER_RE = re.compile(r'(\d+)', re.IGNORECASE)
GENERIC_TERM_SUFFIXES = ('Semester', 'Year', 'Term')


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


def extract_academic_term_index(value):
    text = str(value or '').strip()
    if not text:
        return None

    match = ACADEMIC_TERM_NUMBER_RE.search(text)
    if match is None:
        return None

    return int(match.group(1))


def _unique_case_insensitive(values):
    unique_values = []
    seen = set()

    for value in values:
        text = str(value or '').strip()
        if not text:
            continue

        lowered = text.lower()
        if lowered in seen:
            continue

        seen.add(lowered)
        unique_values.append(text)

    return unique_values


def _resolve_configured_academic_terms(institute_or_terms):
    if institute_or_terms is None:
        return []

    if isinstance(institute_or_terms, (list, tuple, set)):
        return _unique_case_insensitive(institute_or_terms)

    institute_id = getattr(institute_or_terms, 'pk', None)
    if institute_id is None and isinstance(institute_or_terms, int):
        institute_id = institute_or_terms
    if not institute_id:
        return []

    AcademicTerm = apps.get_model('default_activities', 'AcademicTerm')
    return list(
        AcademicTerm.objects
        .filter(institute_id=institute_id)
        .order_by('sort_order', 'id')
        .values_list('name', flat=True)
    )


def canonicalize_academic_term_value(value, institute_or_terms=None):
    text = str(value or '').strip()
    if not text:
        return text

    configured_terms = _resolve_configured_academic_terms(institute_or_terms)
    if not configured_terms:
        return text

    for configured_term in configured_terms:
        if configured_term.lower() == text.lower():
            return configured_term

    index = extract_academic_term_index(text)
    if index is None:
        return text

    for configured_term in configured_terms:
        if extract_academic_term_index(configured_term) == index:
            return configured_term

    return text


def canonicalize_institute_academic_term(institute, value):
    return canonicalize_academic_term_value(value, institute)


def build_academic_term_aliases(value, institute_or_terms=None):
    text = str(value or '').strip()
    if not text:
        return []

    configured_terms = _resolve_configured_academic_terms(institute_or_terms)
    aliases = [text]

    canonical_value = canonicalize_academic_term_value(text, configured_terms)
    if canonical_value:
        aliases.append(canonical_value)

    index = extract_academic_term_index(text)
    if index is not None:
        ordinal = ordinal_label(index)
        for suffix in GENERIC_TERM_SUFFIXES:
            aliases.extend([
                f'{ordinal} {suffix}',
                f'{suffix} {ordinal}',
                f'{index} {suffix}',
                f'{suffix} {index}',
            ])

        aliases.extend(
            configured_term
            for configured_term in configured_terms
            if extract_academic_term_index(configured_term) == index
        )

    return _unique_case_insensitive(aliases)


def build_academic_term_query(field_name, value, institute_or_terms=None):
    aliases = build_academic_term_aliases(value, institute_or_terms)
    if not aliases:
        return None

    query = Q()
    for alias in aliases:
        query |= Q(**{f'{field_name}__iexact': alias})
    return query


def filter_queryset_by_academic_term(queryset, field_name, value, institute_or_terms=None):
    query = build_academic_term_query(field_name, value, institute_or_terms=institute_or_terms)
    if query is None:
        return queryset
    return queryset.filter(query)


def get_academic_terms_for_institute(institute):
    return _resolve_configured_academic_terms(institute)


def _build_alias_lookup(value, institute):
    return {
        alias.lower()
        for alias in build_academic_term_aliases(value, institute)
    }


def _matches_academic_term(value, alias_lookup):
    return str(value or '').strip().lower() in alias_lookup


def _bulk_replace_term_values(queryset, field_name, alias_lookup, new_value):
    objects_to_update = []

    for obj in queryset:
        current_value = getattr(obj, field_name, '')
        if not _matches_academic_term(current_value, alias_lookup):
            continue
        if current_value == new_value:
            continue

        setattr(obj, field_name, new_value)
        objects_to_update.append(obj)

    if not objects_to_update:
        return 0

    queryset.model.objects.bulk_update(objects_to_update, [field_name])
    return len(objects_to_update)


def rename_institute_academic_term(institute, old_value, new_value):
    old_value = str(old_value or '').strip()
    new_value = str(new_value or '').strip()

    if not old_value or not new_value:
        return {'total_updates': 0}

    alias_lookup = _build_alias_lookup(old_value, institute)
    if not alias_lookup:
        return {'total_updates': 0}

    from attendance.models import Attendance
    from published_exam_result.models import PublishedExamResult
    from published_schedules.models import PublishedExamSchedule, PublishedWeeklySchedule
    from published_student.models import PublishedStudent
    from set_exam_data.models import ExamData
    from students.models import StudentCourseAssignment
    from syllabus.models import AcademicTerms
    from weekly_exam_schedule.models import ExamScheduleData, WeeklyScheduleData

    summary = {}
    summary['syllabus_terms'] = _bulk_replace_term_values(
        AcademicTerms.objects.filter(branch__course__institute=institute).only('id', 'name'),
        'name',
        alias_lookup,
        new_value,
    )
    summary['student_course_assignments'] = _bulk_replace_term_values(
        StudentCourseAssignment.objects.filter(student__institute=institute).only('id', 'academic_term'),
        'academic_term',
        alias_lookup,
        new_value,
    )
    summary['attendance'] = _bulk_replace_term_values(
        Attendance.objects.filter(student__institute=institute).only('id', 'year_semester'),
        'year_semester',
        alias_lookup,
        new_value,
    )
    summary['exam_data'] = _bulk_replace_term_values(
        ExamData.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        alias_lookup,
        new_value,
    )
    summary['weekly_schedule_data'] = _bulk_replace_term_values(
        WeeklyScheduleData.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        alias_lookup,
        new_value,
    )
    summary['exam_schedule_data'] = _bulk_replace_term_values(
        ExamScheduleData.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        alias_lookup,
        new_value,
    )
    summary['published_weekly_schedules'] = _bulk_replace_term_values(
        PublishedWeeklySchedule.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        alias_lookup,
        new_value,
    )
    summary['published_exam_schedules'] = _bulk_replace_term_values(
        PublishedExamSchedule.objects.filter(institute=institute).only('id', 'academic_term'),
        'academic_term',
        alias_lookup,
        new_value,
    )

    published_students_to_update = []
    for snapshot in PublishedStudent.objects.filter(institute=institute).only('id', 'student_data'):
        student_data = dict(snapshot.student_data or {})
        course_assignment = dict(student_data.get('course_assignment') or {})
        current_value = course_assignment.get('academic_term', '')

        if not _matches_academic_term(current_value, alias_lookup):
            continue

        course_assignment['academic_term'] = new_value
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
            if _matches_academic_term(current_value, alias_lookup):
                updated_item['academic_term'] = new_value
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
