import math
from collections import OrderedDict, defaultdict

from activity_feed.services import log_activity
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from published_student.models import PublishedStudent
from set_exam_data.models import ObtainedMarks

from .models import PublishedExamResult
from .permissions import PublishedExamResultAccessPermission
from .serializers import PublishedExamResultSerializer


ALREADY_EXISTS_MESSAGE = 'The data already exist.'
NO_OBTAINED_MARKS_MESSAGE = 'No obtained marks found to publish.'
REMOVED_NO_OBTAINED_MARKS_MESSAGE = 'Published exam result removed because no obtained marks are available.'
PUBLISHED_ONLY_FIELDS = (
    'id',
    'institute_id',
    'published_student_id',
    'source_student_id',
    'name',
    'student_personal_id',
    'exam_results',
    'published_at',
    'updated_at',
)


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


def get_published_exam_result_queryset(institute):
    return (
        PublishedExamResult.objects
        .filter(institute=institute)
        .only(*PUBLISHED_ONLY_FIELDS)
        .order_by('source_student_id')
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


def _serialize_obtained_mark(mark):
    total_marks = mark.exam_data.total_marks or 0
    pass_marks = math.ceil(total_marks * 0.4) if total_marks else 0
    return {
        'obtained_marks_id': mark.id,
        'exam_data_id': mark.exam_data_id,
        'subject': mark.exam_data.subject,
        'class_name': mark.exam_data.class_name,
        'branch': mark.exam_data.branch,
        'academic_term': mark.exam_data.academic_term,
        'exam_type': mark.exam_data.exam_type,
        'exam_date': mark.exam_data.date.isoformat() if mark.exam_data.date else None,
        'duration': mark.exam_data.duration,
        'total_marks': total_marks,
        'pass_marks': pass_marks,
        'obtained_marks': mark.obtained_marks,
        'status': 'Pass' if mark.obtained_marks >= pass_marks else 'Fail',
    }


def build_exam_results_map(institute, student_ids):
    if not student_ids:
        return {}

    marks_queryset = (
        ObtainedMarks.objects
        .select_related('exam_data')
        .filter(
            student_id__in=student_ids,
            exam_data__institute=institute,
        )
        .order_by(
            'student_id',
            'exam_data__date',
            'exam_data__academic_term',
            'exam_data__subject',
            'exam_data__exam_type',
            'id',
        )
    )

    results_by_student = defaultdict(list)
    for mark in marks_queryset:
        results_by_student[mark.student_id].append(_serialize_obtained_mark(mark))
    return dict(results_by_student)


def serialize_exam_results(institute, published_student, results_by_student=None):
    if results_by_student is None:
        results_by_student = build_exam_results_map(
            institute,
            [published_student.source_student_id],
        )
    return list(results_by_student.get(published_student.source_student_id, []))


def snapshot_has_changed(existing, published_student, exam_results):
    return any([
        existing.name != published_student.name,
        existing.student_personal_id != published_student.student_personal_id,
        existing.exam_results != exam_results,
        existing.published_student_id != published_student.id,
    ])


def restrict_to_verified_student(request, student_id=None):
    verified_student = getattr(request, '_verified_student', None)
    if verified_student is None:
        return

    if student_id is not None and int(student_id) != verified_student.id:
        raise PermissionDenied('Students can only view their own published exam result.')


class PublishedExamResultListView(APIView):
    permission_classes = [PublishedExamResultAccessPermission]

    def _requested_student_id(self, request):
        return request.query_params.get('student_id') or request.data.get('student_id')

    def _requested_published_student_id(self, request):
        return request.query_params.get('published_student_id') or request.data.get('published_student_id')

    def _sync_snapshot(self, institute, published_student, existing=None, exam_results=None):
        if exam_results is None:
            exam_results = serialize_exam_results(institute, published_student)
        now = timezone.now()

        if not exam_results:
            if existing is None:
                return None, 'skipped'

            existing.delete()
            return existing, 'deleted'

        if existing is None:
            snapshot = PublishedExamResult.objects.create(
                institute_id=institute.id,
                published_student=published_student,
                source_student_id=published_student.source_student_id,
                name=published_student.name,
                student_personal_id=published_student.student_personal_id,
                exam_results=exam_results,
                published_at=now,
                updated_at=now,
            )
            return snapshot, 'created'

        if not snapshot_has_changed(existing, published_student, exam_results):
            return existing, 'already_exists'

        existing.published_student = published_student
        existing.source_student_id = published_student.source_student_id
        existing.name = published_student.name
        existing.student_personal_id = published_student.student_personal_id
        existing.exam_results = exam_results
        existing.updated_at = now
        existing.save(
            update_fields=[
                'published_student',
                'source_student_id',
                'name',
                'student_personal_id',
                'exam_results',
                'updated_at',
            ]
        )
        return existing, 'updated'

    def get(self, request):
        institute = request._verified_institute
        requested_student_id = self._requested_student_id(request)
        requested_published_student_id = self._requested_published_student_id(request)

        queryset = get_published_exam_result_queryset(institute)
        if requested_student_id:
            queryset = queryset.filter(source_student_id=requested_student_id)
        if requested_published_student_id:
            queryset = queryset.filter(published_student_id=requested_published_student_id)

        verified_student = getattr(request, '_verified_student', None)
        if verified_student is not None:
            queryset = queryset.filter(source_student_id=verified_student.id)

        serializer = PublishedExamResultSerializer(
            queryset,
            many=True,
        )
        return Response(build_institute_response(institute, serializer.data))

    def post(self, request):
        institute = request._verified_institute
        requested_student_id = self._requested_student_id(request)
        requested_published_student_id = self._requested_published_student_id(request)

        if requested_student_id or requested_published_student_id:
            published_student = get_published_student_queryset(
                institute,
                student_id=requested_student_id,
                published_student_id=requested_published_student_id,
            ).first()
            if published_student is None:
                return Response(
                    {'detail': 'Published student not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            existing = PublishedExamResult.objects.filter(
                institute=institute,
                source_student_id=published_student.source_student_id,
            ).only(*PUBLISHED_ONLY_FIELDS).first()
            snapshot, action = self._sync_snapshot(institute, published_student, existing=existing)

            response_kwargs = {
                'created_count': 1 if action == 'created' else 0,
                'updated_count': 1 if action == 'updated' else 0,
                'already_exists_count': 1 if action == 'already_exists' else 0,
                'deleted_count': 1 if action == 'deleted' else 0,
            }
            if action == 'already_exists':
                response_kwargs['message'] = ALREADY_EXISTS_MESSAGE
                response_kwargs['detail'] = ALREADY_EXISTS_MESSAGE
            elif action == 'skipped':
                response_kwargs['message'] = NO_OBTAINED_MARKS_MESSAGE
                response_kwargs['detail'] = NO_OBTAINED_MARKS_MESSAGE
            elif action == 'deleted':
                response_kwargs['message'] = REMOVED_NO_OBTAINED_MARKS_MESSAGE
                response_kwargs['detail'] = REMOVED_NO_OBTAINED_MARKS_MESSAGE

            serialized_results = (
                [PublishedExamResultSerializer(snapshot).data]
                if action in {'created', 'updated', 'already_exists'}
                else []
            )
            description = {
                'created': f"Synced published exam result for {published_student.name}.",
                'updated': f"Synced published exam result for {published_student.name}.",
                'already_exists': f"Published exam result for {published_student.name} is already up to date.",
                'skipped': f"Skipped published exam result for {published_student.name} because no obtained marks were found.",
                'deleted': f"Removed published exam result for {published_student.name} because no obtained marks were found.",
            }[action]

            log_activity(
                request,
                action='sync',
                entity_type='published exam result',
                entity_id=snapshot.id if snapshot is not None else None,
                entity_name=published_student.name,
                description=description,
                details=response_kwargs,
            )
            return Response(
                build_institute_response(institute, serialized_results, **response_kwargs),
                status=status.HTTP_200_OK,
            )

        published_students = list(get_published_student_queryset(institute))
        existing_map = {
            snapshot.source_student_id: snapshot
            for snapshot in PublishedExamResult.objects.filter(institute=institute).only(*PUBLISHED_ONLY_FIELDS)
        }

        current_student_ids = set()
        create_objects = []
        update_objects = []
        already_exists_count = 0
        now = timezone.now()

        results_by_student = build_exam_results_map(
            institute,
            [published_student.source_student_id for published_student in published_students],
        )

        for published_student in published_students:
            exam_results = results_by_student.get(published_student.source_student_id, [])
            if not exam_results:
                continue

            current_student_ids.add(published_student.source_student_id)
            existing = existing_map.get(published_student.source_student_id)

            if existing is None:
                create_objects.append(
                    PublishedExamResult(
                        institute_id=institute.id,
                        published_student=published_student,
                        source_student_id=published_student.source_student_id,
                        name=published_student.name,
                        student_personal_id=published_student.student_personal_id,
                        exam_results=exam_results,
                        published_at=now,
                        updated_at=now,
                    )
                )
                continue

            if not snapshot_has_changed(existing, published_student, exam_results):
                already_exists_count += 1
                continue

            existing.published_student = published_student
            existing.source_student_id = published_student.source_student_id
            existing.name = published_student.name
            existing.student_personal_id = published_student.student_personal_id
            existing.exam_results = exam_results
            existing.updated_at = now
            update_objects.append(existing)

        if create_objects:
            PublishedExamResult.objects.bulk_create(create_objects)
        if update_objects:
            PublishedExamResult.objects.bulk_update(
                update_objects,
                ['published_student', 'source_student_id', 'name', 'student_personal_id', 'exam_results', 'updated_at'],
            )

        stale_student_ids = set(existing_map).difference(current_student_ids)
        deleted_count = len(stale_student_ids)
        if deleted_count:
            PublishedExamResult.objects.filter(
                institute=institute,
                source_student_id__in=stale_student_ids,
            ).delete()

        serializer = PublishedExamResultSerializer(
            get_published_exam_result_queryset(institute),
            many=True,
        )
        response_kwargs = {
            'created_count': len(create_objects),
            'updated_count': len(update_objects),
            'already_exists_count': already_exists_count,
            'deleted_count': deleted_count,
        }
        if not create_objects and not update_objects and not deleted_count and already_exists_count:
            response_kwargs['message'] = ALREADY_EXISTS_MESSAGE
            response_kwargs['detail'] = ALREADY_EXISTS_MESSAGE
        elif not create_objects and not update_objects and not deleted_count and not already_exists_count:
            response_kwargs['message'] = NO_OBTAINED_MARKS_MESSAGE
            response_kwargs['detail'] = NO_OBTAINED_MARKS_MESSAGE

        log_activity(
            request,
            action='sync',
            entity_type='published exam result',
            description=(
                f"Synced published exam results. Created {len(create_objects)}, updated {len(update_objects)}, removed {deleted_count}."
            ),
            details=response_kwargs,
        )
        return Response(
            build_institute_response(institute, serializer.data, **response_kwargs),
            status=status.HTTP_200_OK,
        )


class PublishedExamResultDetailView(APIView):
    permission_classes = [PublishedExamResultAccessPermission]

    def _get_snapshot(self, institute, student_id):
        return get_published_exam_result_queryset(institute).get(source_student_id=student_id)

    def get(self, request, student_id):
        institute = request._verified_institute
        restrict_to_verified_student(request, student_id)
        try:
            snapshot = self._get_snapshot(institute, student_id)
        except PublishedExamResult.DoesNotExist:
            return Response(
                {'detail': 'Published exam result not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(PublishedExamResultSerializer(snapshot).data)

    def put(self, request, student_id):
        return self._refresh(request, student_id)

    def patch(self, request, student_id):
        return self._refresh(request, student_id)

    def _refresh(self, request, student_id):
        institute = request._verified_institute

        try:
            snapshot = self._get_snapshot(institute, student_id)
        except PublishedExamResult.DoesNotExist:
            return Response(
                {'detail': 'Published exam result not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            published_student = get_published_student_queryset(
                institute,
                student_id=student_id,
            ).get()
        except PublishedStudent.DoesNotExist:
            return Response(
                {'detail': 'Published student not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        snapshot, action = PublishedExamResultListView()._sync_snapshot(
            institute,
            published_student,
            existing=snapshot,
        )

        if action == 'deleted':
            return Response(
                {
                    'detail': REMOVED_NO_OBTAINED_MARKS_MESSAGE,
                    'message': REMOVED_NO_OBTAINED_MARKS_MESSAGE,
                },
                status=status.HTTP_200_OK,
            )

        if action == 'skipped':
            return Response(
                {
                    'detail': NO_OBTAINED_MARKS_MESSAGE,
                    'message': NO_OBTAINED_MARKS_MESSAGE,
                },
                status=status.HTTP_200_OK,
            )

        serializer = PublishedExamResultSerializer(snapshot)
        response_data = dict(serializer.data)
        response_data['message'] = (
            'Published exam result updated successfully.'
            if action == 'updated'
            else ALREADY_EXISTS_MESSAGE
        )
        return Response(response_data, status=status.HTTP_200_OK)

    def delete(self, request, student_id):
        institute = request._verified_institute
        try:
            snapshot = self._get_snapshot(institute, student_id)
        except PublishedExamResult.DoesNotExist:
            return Response(
                {'detail': 'Published exam result not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        deleted_id = snapshot.id
        deleted_name = snapshot.name
        snapshot.delete()
        log_activity(
            request,
            action='delete',
            entity_type='published exam result',
            entity_id=deleted_id,
            entity_name=deleted_name,
            description=f"Deleted published exam result for {deleted_name}.",
            details={'student_id': student_id},
        )
        return Response(
            {'detail': 'Published exam result deleted successfully.'},
            status=status.HTTP_200_OK,
        )
