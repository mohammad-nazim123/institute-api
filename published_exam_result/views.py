from collections import OrderedDict, defaultdict

from activity_feed.services import log_activity
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from iinstitutes_list.academic_terms import filter_queryset_by_academic_term
from published_student.models import PublishedStudent
from set_exam_data.models import ObtainedMarks

from .models import PublishedExamData, PublishedObtainedMarks
from .permissions import PublishedExamResultAccessPermission
from .serializers import PublishedExamResultSerializer


ALREADY_EXISTS_MESSAGE = 'The data already exist.'
NO_OBTAINED_MARKS_MESSAGE = 'No obtained marks found to publish.'
REMOVED_NO_OBTAINED_MARKS_MESSAGE = 'Published exam result removed because no obtained marks are available.'
SYNCED_MESSAGE = 'Published exam result synced successfully.'
UPDATED_MESSAGE = 'Published exam result updated successfully.'
DELETED_MESSAGE = 'Published exam result deleted successfully.'
SCOPE_FILTER_KEYS = ('class_name', 'branch', 'academic_term', 'exam_type', 'subject')
PUBLISHED_RESULTS_ORDERING = (
    'published_student__source_student_id',
    'published_exam_data__date',
    'published_exam_data__academic_term',
    'published_exam_data__exam_type',
    'published_exam_data__subject',
    'id',
)


def build_institute_response(institute, published_exam_results, **extra):
    payload = OrderedDict([
        ('id', institute.id),
        ('name', institute.name),
        ('published_exam_results', published_exam_results),
    ])
    for key, value in extra.items():
        payload[key] = value
    return payload


def normalize_lookup_value(value):
    text = str(value or '').strip()
    return text or None


def parse_optional_int(value):
    if value in (None, ''):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def request_value(request, key):
    query_value = request.query_params.get(key)
    if query_value not in (None, ''):
        return query_value

    data = getattr(request, 'data', None)
    if isinstance(data, dict):
        data_value = data.get(key)
        if data_value not in (None, ''):
            return data_value

    return None


def get_requested_filters(request):
    filters = {
        'student_id': parse_optional_int(request_value(request, 'student_id')),
        'published_student_id': parse_optional_int(request_value(request, 'published_student_id')),
    }
    for key in SCOPE_FILTER_KEYS:
        filters[key] = normalize_lookup_value(request_value(request, key))
    return filters


def get_requested_scope(filters):
    return {key: filters.get(key) for key in SCOPE_FILTER_KEYS}


def apply_scope_filters(queryset, institute, scope, *, prefix=''):
    class_name = scope.get('class_name')
    branch = scope.get('branch')
    academic_term = scope.get('academic_term')
    exam_type = scope.get('exam_type')
    subject = scope.get('subject')

    if class_name:
        queryset = queryset.filter(**{f'{prefix}class_name__iexact': class_name})
    if branch:
        queryset = queryset.filter(**{f'{prefix}branch__iexact': branch})
    if exam_type:
        queryset = queryset.filter(**{f'{prefix}exam_type__iexact': exam_type})
    if subject:
        queryset = queryset.filter(**{f'{prefix}subject__iexact': subject})
    if academic_term:
        queryset = filter_queryset_by_academic_term(
            queryset,
            f'{prefix}academic_term',
            academic_term,
            institute,
        )
    return queryset


def get_published_student_queryset(institute, *, student_id=None, published_student_id=None):
    queryset = (
        PublishedStudent.objects
        .filter(institute=institute)
        .only('id', 'institute_id', 'source_student_id', 'name', 'student_personal_id')
        .order_by('source_student_id')
    )
    if student_id is not None:
        queryset = queryset.filter(source_student_id=student_id)
    if published_student_id is not None:
        queryset = queryset.filter(pk=published_student_id)
    return queryset


def get_published_results_queryset(institute, *, student_id=None, published_student_id=None, scope=None):
    queryset = (
        PublishedObtainedMarks.objects
        .select_related('published_exam_data', 'published_student')
        .filter(
            published_exam_data__institute=institute,
            published_student__institute=institute,
        )
    )
    if student_id is not None:
        queryset = queryset.filter(published_student__source_student_id=student_id)
    if published_student_id is not None:
        queryset = queryset.filter(published_student_id=published_student_id)
    queryset = apply_scope_filters(queryset, institute, scope or {}, prefix='published_exam_data__')
    return queryset.order_by(*PUBLISHED_RESULTS_ORDERING)


def get_source_marks_queryset(institute, *, student_id=None, student_ids=None, scope=None):
    queryset = (
        ObtainedMarks.objects
        .select_related('exam_data')
        .filter(exam_data__institute=institute)
        .order_by(
            'student_id',
            'exam_data__date',
            'exam_data__academic_term',
            'exam_data__exam_type',
            'exam_data__subject',
            'id',
        )
    )
    if student_id is not None:
        queryset = queryset.filter(student_id=student_id)
    elif student_ids is not None:
        queryset = queryset.filter(student_id__in=student_ids)
    queryset = apply_scope_filters(queryset, institute, scope or {}, prefix='exam_data__')
    return queryset


def serialize_published_results(rows):
    return PublishedExamResultSerializer(rows, many=True).data


def cleanup_orphaned_published_exam_data(published_exam_data_ids):
    candidate_ids = {published_exam_data_id for published_exam_data_id in published_exam_data_ids if published_exam_data_id}
    if not candidate_ids:
        return 0

    orphan_ids = list(
        PublishedExamData.objects
        .filter(id__in=candidate_ids, published_obtained_marks__isnull=True)
        .values_list('id', flat=True)
    )
    if orphan_ids:
        PublishedExamData.objects.filter(id__in=orphan_ids).delete()
    return len(orphan_ids)


def sync_published_exam_data_from_source(exam_data, now, published_exam_data_cache=None):
    published_exam_data = None
    if published_exam_data_cache is not None:
        published_exam_data = published_exam_data_cache.get(exam_data.id)

    if published_exam_data is None:
        published_exam_data = PublishedExamData.objects.filter(source_exam_data_id=exam_data.id).first()
        if published_exam_data_cache is not None and published_exam_data is not None:
            published_exam_data_cache[exam_data.id] = published_exam_data

    if published_exam_data is None:
        published_exam_data = PublishedExamData.objects.create(
            institute_id=exam_data.institute_id,
            source_exam_data_id=exam_data.id,
            class_name=exam_data.class_name or '',
            branch=exam_data.branch or '',
            academic_term=exam_data.academic_term or '',
            subject=exam_data.subject or '',
            exam_type=exam_data.exam_type or '',
            date=exam_data.date,
            duration=exam_data.duration or 0,
            total_marks=exam_data.total_marks or 0,
            published_at=now,
            updated_at=now,
        )
        if published_exam_data_cache is not None:
            published_exam_data_cache[exam_data.id] = published_exam_data
        return published_exam_data, 'created'

    update_fields = []
    values = {
        'institute_id': exam_data.institute_id,
        'class_name': exam_data.class_name or '',
        'branch': exam_data.branch or '',
        'academic_term': exam_data.academic_term or '',
        'subject': exam_data.subject or '',
        'exam_type': exam_data.exam_type or '',
        'date': exam_data.date,
        'duration': exam_data.duration or 0,
        'total_marks': exam_data.total_marks or 0,
    }

    for field_name, expected_value in values.items():
        if getattr(published_exam_data, field_name) != expected_value:
            setattr(published_exam_data, field_name, expected_value)
            update_fields.append(field_name)

    if not update_fields:
        return published_exam_data, 'already_exists'

    published_exam_data.updated_at = now
    update_fields.append('updated_at')
    published_exam_data.save(update_fields=update_fields)
    return published_exam_data, 'updated'


def sync_published_student_scope(
    institute,
    published_student,
    *,
    scope,
    source_marks,
    existing_rows,
    now,
    published_exam_data_cache=None,
):
    source_marks = list(source_marks or [])
    existing_rows = list(existing_rows or [])

    if not source_marks:
        if not existing_rows:
            return {'action': 'skipped', 'rows': []}

        stale_exam_data_ids = [row.published_exam_data_id for row in existing_rows]
        PublishedObtainedMarks.objects.filter(id__in=[row.id for row in existing_rows]).delete()
        cleanup_orphaned_published_exam_data(stale_exam_data_ids)
        return {'action': 'deleted', 'rows': []}

    existing_by_source_id = {
        row.source_obtained_marks_id: row
        for row in existing_rows
    }
    current_source_ids = set()
    create_rows = []
    update_rows = []
    published_exam_data_changed = False

    for mark in source_marks:
        current_source_ids.add(mark.id)
        published_exam_data, exam_data_action = sync_published_exam_data_from_source(
            mark.exam_data,
            now,
            published_exam_data_cache=published_exam_data_cache,
        )
        if exam_data_action != 'already_exists':
            published_exam_data_changed = True

        existing = existing_by_source_id.get(mark.id)
        if existing is None:
            create_rows.append(
                PublishedObtainedMarks(
                    published_exam_data=published_exam_data,
                    published_student=published_student,
                    source_obtained_marks_id=mark.id,
                    obtained_marks=mark.obtained_marks,
                    published_at=now,
                    updated_at=now,
                )
            )
            continue

        row_changed = False
        if existing.published_exam_data_id != published_exam_data.id:
            existing.published_exam_data = published_exam_data
            row_changed = True
        if existing.published_student_id != published_student.id:
            existing.published_student = published_student
            row_changed = True
        if existing.obtained_marks != mark.obtained_marks:
            existing.obtained_marks = mark.obtained_marks
            row_changed = True

        if row_changed:
            existing.updated_at = now
            update_rows.append(existing)

    if create_rows:
        PublishedObtainedMarks.objects.bulk_create(create_rows)

    if update_rows:
        PublishedObtainedMarks.objects.bulk_update(
            update_rows,
            ['published_exam_data', 'published_student', 'obtained_marks', 'updated_at'],
        )

    stale_rows = [
        row for row in existing_rows
        if row.source_obtained_marks_id not in current_source_ids
    ]
    if stale_rows:
        stale_exam_data_ids = [row.published_exam_data_id for row in stale_rows]
        PublishedObtainedMarks.objects.filter(id__in=[row.id for row in stale_rows]).delete()
        cleanup_orphaned_published_exam_data(stale_exam_data_ids)

    had_existing_rows = bool(existing_rows)
    changed = bool(create_rows or update_rows or stale_rows or published_exam_data_changed)
    if not had_existing_rows:
        action = 'created'
    elif changed:
        action = 'updated'
    else:
        action = 'already_exists'

    rows = list(
        get_published_results_queryset(
            institute,
            student_id=published_student.source_student_id,
            published_student_id=published_student.id,
            scope=scope,
        )
    )
    return {'action': action, 'rows': rows}


def get_action_counts(action):
    return {
        'created_count': 1 if action == 'created' else 0,
        'updated_count': 1 if action == 'updated' else 0,
        'already_exists_count': 1 if action == 'already_exists' else 0,
        'deleted_count': 1 if action == 'deleted' else 0,
    }


def get_action_message(action):
    return {
        'created': SYNCED_MESSAGE,
        'updated': UPDATED_MESSAGE,
        'already_exists': ALREADY_EXISTS_MESSAGE,
        'skipped': NO_OBTAINED_MARKS_MESSAGE,
        'deleted': REMOVED_NO_OBTAINED_MARKS_MESSAGE,
    }[action]


def restrict_to_verified_student(request, student_id=None):
    verified_student = getattr(request, '_verified_student', None)
    if verified_student is None:
        return

    if student_id is not None and int(student_id) != verified_student.id:
        raise PermissionDenied('Students can only view their own published exam result.')


class PublishedExamResultListView(APIView):
    permission_classes = [PublishedExamResultAccessPermission]

    def get(self, request):
        institute = request._verified_institute
        filters = get_requested_filters(request)
        requested_student_id = filters['student_id']
        requested_published_student_id = filters['published_student_id']
        scope = get_requested_scope(filters)

        verified_student = getattr(request, '_verified_student', None)
        if verified_student is not None:
            restrict_to_verified_student(request, requested_student_id)
            requested_student_id = verified_student.id

        queryset = get_published_results_queryset(
            institute,
            student_id=requested_student_id,
            published_student_id=requested_published_student_id,
            scope=scope,
        )
        return Response(
            build_institute_response(
                institute,
                serialize_published_results(queryset),
            )
        )

    def post(self, request):
        institute = request._verified_institute
        filters = get_requested_filters(request)
        requested_student_id = filters['student_id']
        requested_published_student_id = filters['published_student_id']
        scope = get_requested_scope(filters)

        published_students = list(
            get_published_student_queryset(
                institute,
                student_id=requested_student_id,
                published_student_id=requested_published_student_id,
            )
        )

        if (requested_student_id is not None or requested_published_student_id is not None) and not published_students:
            return Response(
                {'detail': 'Published student not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        student_ids = [published_student.source_student_id for published_student in published_students]
        source_marks = list(
            get_source_marks_queryset(
                institute,
                student_ids=student_ids,
                scope=scope,
            )
        ) if student_ids else []
        source_marks_by_student = defaultdict(list)
        for mark in source_marks:
            source_marks_by_student[mark.student_id].append(mark)

        existing_rows_queryset = get_published_results_queryset(
            institute,
            scope=scope,
        )
        if published_students:
            existing_rows_queryset = existing_rows_queryset.filter(published_student__in=published_students)
        else:
            existing_rows_queryset = existing_rows_queryset.none()

        existing_rows_by_student = defaultdict(list)
        for row in existing_rows_queryset:
            existing_rows_by_student[row.published_student.source_student_id].append(row)

        source_exam_data_ids = {
            mark.exam_data_id
            for mark in source_marks
        }
        published_exam_data_cache = {
            item.source_exam_data_id: item
            for item in PublishedExamData.objects.filter(source_exam_data_id__in=source_exam_data_ids)
        } if source_exam_data_ids else {}

        results = []
        with transaction.atomic():
            now = timezone.now()
            for published_student in published_students:
                result = sync_published_student_scope(
                    institute,
                    published_student,
                    scope=scope,
                    source_marks=source_marks_by_student.get(published_student.source_student_id, []),
                    existing_rows=existing_rows_by_student.get(published_student.source_student_id, []),
                    now=now,
                    published_exam_data_cache=published_exam_data_cache,
                )
                results.append((published_student, result))

        created_count = sum(1 for _, result in results if result['action'] == 'created')
        updated_count = sum(1 for _, result in results if result['action'] == 'updated')
        already_exists_count = sum(1 for _, result in results if result['action'] == 'already_exists')
        deleted_count = sum(1 for _, result in results if result['action'] == 'deleted')

        response_kwargs = {
            'created_count': created_count,
            'updated_count': updated_count,
            'already_exists_count': already_exists_count,
            'deleted_count': deleted_count,
        }

        if len(results) == 1:
            published_student, result = results[0]
            action = result['action']
            message = get_action_message(action)
            response_kwargs['message'] = message
            response_kwargs['detail'] = message

            serialized_rows = serialize_published_results(result['rows'])
            log_activity(
                request,
                action='sync',
                entity_type='published exam result',
                entity_id=serialized_rows[0]['id'] if serialized_rows else None,
                entity_name=published_student.name,
                description=(
                    f"Synced published exam result for {published_student.name}."
                    if action in {'created', 'updated'}
                    else f"Processed published exam result for {published_student.name}: {message}"
                ),
                details={**response_kwargs, **scope},
            )
            return Response(
                build_institute_response(institute, serialized_rows, **response_kwargs),
                status=status.HTTP_200_OK,
            )

        if not created_count and not updated_count and not deleted_count and already_exists_count:
            response_kwargs['message'] = ALREADY_EXISTS_MESSAGE
            response_kwargs['detail'] = ALREADY_EXISTS_MESSAGE
        elif not created_count and not updated_count and not deleted_count and not already_exists_count:
            response_kwargs['message'] = NO_OBTAINED_MARKS_MESSAGE
            response_kwargs['detail'] = NO_OBTAINED_MARKS_MESSAGE

        serialized_rows = serialize_published_results(
            get_published_results_queryset(
                institute,
                scope=scope,
            )
        )
        log_activity(
            request,
            action='sync',
            entity_type='published exam result',
            description=(
                f"Synced published exam results. Created {created_count}, updated {updated_count}, "
                f"already up to date {already_exists_count}, removed {deleted_count}."
            ),
            details={**response_kwargs, **scope},
        )
        return Response(
            build_institute_response(institute, serialized_rows, **response_kwargs),
            status=status.HTTP_200_OK,
        )


class PublishedExamResultDetailView(APIView):
    permission_classes = [PublishedExamResultAccessPermission]

    def get(self, request, student_id):
        institute = request._verified_institute
        restrict_to_verified_student(request, student_id)

        filters = get_requested_filters(request)
        scope = get_requested_scope(filters)
        rows = list(
            get_published_results_queryset(
                institute,
                student_id=student_id,
                published_student_id=filters['published_student_id'],
                scope=scope,
            )
        )
        if not rows:
            return Response(
                {'detail': 'Published exam result not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            build_institute_response(
                institute,
                serialize_published_results(rows),
            )
        )

    def put(self, request, student_id):
        return self._refresh(request, student_id)

    def patch(self, request, student_id):
        return self._refresh(request, student_id)

    def _refresh(self, request, student_id):
        institute = request._verified_institute
        filters = get_requested_filters(request)
        scope = get_requested_scope(filters)

        published_student = get_published_student_queryset(
            institute,
            student_id=student_id,
            published_student_id=filters['published_student_id'],
        ).first()
        if published_student is None:
            return Response(
                {'detail': 'Published student not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        source_marks = list(
            get_source_marks_queryset(
                institute,
                student_id=published_student.source_student_id,
                scope=scope,
            )
        )
        existing_rows = list(
            get_published_results_queryset(
                institute,
                student_id=published_student.source_student_id,
                published_student_id=published_student.id,
                scope=scope,
            )
        )
        source_exam_data_ids = {mark.exam_data_id for mark in source_marks}
        published_exam_data_cache = {
            item.source_exam_data_id: item
            for item in PublishedExamData.objects.filter(source_exam_data_id__in=source_exam_data_ids)
        } if source_exam_data_ids else {}

        with transaction.atomic():
            result = sync_published_student_scope(
                institute,
                published_student,
                scope=scope,
                source_marks=source_marks,
                existing_rows=existing_rows,
                now=timezone.now(),
                published_exam_data_cache=published_exam_data_cache,
            )

        action = result['action']
        counts = get_action_counts(action)
        message = get_action_message(action)
        response_kwargs = {
            **counts,
            'message': message,
            'detail': message,
        }
        serialized_rows = serialize_published_results(result['rows'])
        return Response(
            build_institute_response(institute, serialized_rows, **response_kwargs),
            status=status.HTTP_200_OK,
        )

    def delete(self, request, student_id):
        institute = request._verified_institute
        filters = get_requested_filters(request)
        scope = get_requested_scope(filters)

        rows = list(
            get_published_results_queryset(
                institute,
                student_id=student_id,
                published_student_id=filters['published_student_id'],
                scope=scope,
            )
        )
        if not rows:
            return Response(
                {'detail': 'Published exam result not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        deleted_exam_data_ids = [row.published_exam_data_id for row in rows]
        deleted_name = rows[0].published_student.name
        with transaction.atomic():
            PublishedObtainedMarks.objects.filter(id__in=[row.id for row in rows]).delete()
            cleanup_orphaned_published_exam_data(deleted_exam_data_ids)

        log_activity(
            request,
            action='delete',
            entity_type='published exam result',
            entity_name=deleted_name,
            description=f"Deleted published exam result for {deleted_name}.",
            details={'student_id': student_id, **scope},
        )
        return Response(
            {'detail': DELETED_MESSAGE},
            status=status.HTTP_200_OK,
        )
