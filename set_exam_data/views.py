from rest_framework import status

from activity_feed.services import log_activity
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    STUDENT_ACCESS_CONTROL,
    SchedulePermission,
)
from iinstitutes_list.academic_terms import (
    canonicalize_institute_academic_term,
    filter_queryset_by_academic_term,
)
from students.models import Student

from .models import ExamData, ObtainedMarks
from .serializers import ExamDataItemSerializer, ExamDictionarySerializer, ObtainedMarksSerializer


class ExamDataMixin:
    """Shared helpers for hierarchy resolution and dictionary response."""
    permission_classes = [SchedulePermission]
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def _hierarchy(self, request):
        body = request.data if hasattr(request, 'data') else {}
        institute = getattr(request, '_verified_institute', None)
        return {
            'class_name': request.query_params.get('class_name') or body.get('class_name') or body.get('class'),
            'branch':     request.query_params.get('branch')     or body.get('branch'),
            'academic_term': canonicalize_institute_academic_term(
                institute,
                request.query_params.get('academic_term') or body.get('academic_term') or body.get('academic_terms'),
            ),
        }

    def _require_hierarchy(self, request):
        h = self._hierarchy(request)
        missing = [k for k, v in h.items() if not v]
        if missing:
            raise ValidationError({f: ['This field is required.'] for f in missing})
        return h

    def _queryset(self, institute, h):
        queryset = (
            ExamData.objects
            .filter(
                institute=institute,
                class_name=h['class_name'],
                branch=h['branch'],
            )
            .order_by('id')
        )
        return filter_queryset_by_academic_term(
            queryset,
            'academic_term',
            h['academic_term'],
            institute,
        )

    def _dict_response(self, institute, h):
        qs = self._queryset(institute, h)
        data = {
            'institute': institute,
            'class_name': h['class_name'],
            'branch': h['branch'],
            'academic_term': h['academic_term'],
            'exam_data': qs,
        }
        return Response(ExamDictionarySerializer().to_representation(data))


class ExamDataView(ExamDataMixin, APIView):
    """
    Flat CRUD for exam data, scoped by institute + class + branch + academic_term.

    GET    ?institute=<id>&class_name=<>&branch=<>&academic_term=<>
           → flat dict of all exam subjects for that hierarchy

    POST   ?institute=<id>
           body: { class_name, branch, academic_term, subject, exam_type, date, duration, total_marks }
           OR list: [ {...}, {...} ]   → bulk create

    PUT    <pk>/?institute=<id>
           body: { class_name, branch, academic_term, subject, exam_type, date, duration, total_marks }
           → full replace of that exam entry, returns updated dict

    PATCH  <pk>/?institute=<id>
           body: any subset of fields
           → partial update, returns updated dict

    DELETE <pk>/?institute=<id>&class_name=<>&branch=<>&academic_term=<>
           → delete entry, returns updated dict
    """

    def get(self, request):
        institute = request._verified_institute
        h = self._require_hierarchy(request)
        return self._dict_response(institute, h)

    def post(self, request):
        institute = request._verified_institute
        h = self._require_hierarchy(request)

        payload = request.data
        many = isinstance(payload, list)

        if many:
            items = []
            for item in payload:
                ser = ExamDataItemSerializer(data=item)
                ser.is_valid(raise_exception=True)
                items.append(ExamData(
                    institute=institute,
                    class_name=h['class_name'],
                    branch=h['branch'],
                    academic_term=h['academic_term'],
                    **ser.validated_data,
                ))
            created_items = ExamData.objects.bulk_create(items)
            log_activity(
                request,
                action='create',
                entity_type='exam data',
                description=f"Added {len(created_items)} exam entries for {h['class_name']} / {h['branch']} / {h['academic_term']}.",
                details={'count': len(created_items), **h},
            )
        else:
            ser = ExamDataItemSerializer(data=payload)
            ser.is_valid(raise_exception=True)
            entry = ExamData.objects.create(
                institute=institute,
                class_name=h['class_name'],
                branch=h['branch'],
                academic_term=h['academic_term'],
                **ser.validated_data,
            )
            log_activity(
                request,
                action='create',
                entity_type='exam data',
                entity_id=entry.id,
                entity_name=entry.subject,
                description=f"Added exam data for {entry.subject} in {h['class_name']} / {h['branch']} / {h['academic_term']}.",
                details={**h, 'exam_type': entry.exam_type},
            )

        return self._dict_response(institute, h)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        institute = request._verified_institute
        try:
            entry = ExamData.objects.get(pk=pk, institute=institute)
        except ExamData.DoesNotExist:
            return Response({'detail': 'Exam data not found.'}, status=status.HTTP_404_NOT_FOUND)

        ser = ExamDataItemSerializer(entry, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        ser.save()
        log_activity(
            request,
            action='update',
            entity_type='exam data',
            entity_id=entry.id,
            entity_name=entry.subject,
            description=f"Updated exam data for {entry.subject}.",
            details={
                'class_name': entry.class_name,
                'branch': entry.branch,
                'academic_term': entry.academic_term,
                'exam_type': entry.exam_type,
            },
        )

        # Use the hierarchy from the saved entry (supports class/branch from the row)
        h = {
            'class_name': entry.class_name,
            'branch': entry.branch,
            'academic_term': entry.academic_term,
        }
        return self._dict_response(institute, h)

    def delete(self, request, pk):
        institute = request._verified_institute
        try:
            entry = ExamData.objects.get(pk=pk, institute=institute)
        except ExamData.DoesNotExist:
            return Response({'detail': 'Exam data not found.'}, status=status.HTTP_404_NOT_FOUND)

        h = {
            'class_name': entry.class_name,
            'branch': entry.branch,
            'academic_term': entry.academic_term,
        }
        deleted_payload = {
            'entity_id': entry.id,
            'entity_name': entry.subject,
            'details': {**h, 'exam_type': entry.exam_type},
        }
        entry.delete()
        log_activity(
            request,
            action='delete',
            entity_type='exam data',
            entity_id=deleted_payload['entity_id'],
            entity_name=deleted_payload['entity_name'],
            description=f"Deleted exam data for {deleted_payload['entity_name']}.",
            details=deleted_payload['details'],
        )
        return self._dict_response(institute, h)


class ObtainedMarksView(ExamDataMixin, APIView):
    """
    CRUD for obtained marks (student results).

    GET    ?institute=<id>&class_name=<>&branch=<>&academic_term=<>  → all marks for that hierarchy
           Optional filters: &student=<id>  &exam_data=<id>

    POST   ?institute=<id>
           body: { exam_data, student, obtained_marks }
           OR list: [ {...}, {...} ]

    PUT    <pk>/?institute=<id>
           body: { obtained_marks }

    PATCH  <pk>/?institute=<id>
           partial update

    DELETE <pk>/?institute=<id>
    """

    def _marks_queryset(self, institute, request):
        qs = ObtainedMarks.objects.select_related(
            'student', 'exam_data'
        ).filter(exam_data__institute=institute)

        for param, lookup in [
            ('class_name',    'exam_data__class_name'),
            ('branch',        'exam_data__branch'),
            ('student',       'student_id'),
            ('exam_data',     'exam_data_id'),
        ]:
            val = request.query_params.get(param)
            if val:
                qs = qs.filter(**{lookup: val})
        academic_term = request.query_params.get('academic_term')
        if academic_term:
            qs = filter_queryset_by_academic_term(
                qs,
                'exam_data__academic_term',
                academic_term,
                institute,
            )
        return qs

    def get(self, request, pk=None):
        institute = request._verified_institute
        verified_student = getattr(request, '_verified_student', None)

        if pk is not None:
            try:
                obj = ObtainedMarks.objects.select_related('student', 'exam_data').get(
                    pk=pk, exam_data__institute=institute
                )
            except ObtainedMarks.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(ObtainedMarksSerializer(obj).data)

        qs = self._marks_queryset(institute, request)
        if verified_student:
            qs = qs.filter(student=verified_student)
        return Response(ObtainedMarksSerializer(qs, many=True).data)

    def post(self, request, pk=None):
        if getattr(request, '_verified_student', None):
            return Response({'detail': 'Students cannot write marks.'}, status=status.HTTP_403_FORBIDDEN)

        institute = request._verified_institute
        payload = request.data
        many = isinstance(payload, list)

        if many:
            # Validate all first, then bulk_create
            validated = []
            for item in payload:
                ser = ObtainedMarksSerializer(data=item)
                ser.is_valid(raise_exception=True)
                validated.append(ser.validated_data)

            # Verify all exam_data belong to this institute (1 query)
            exam_data_ids = {v['exam_data'].id for v in validated}
            valid_ids = set(
                ExamData.objects.filter(pk__in=exam_data_ids, institute=institute).values_list('id', flat=True)
            )
            bad = exam_data_ids - valid_ids
            if bad:
                return Response({'detail': f'exam_data ids {bad} do not belong to your institute.'}, status=status.HTTP_403_FORBIDDEN)

            objs = ObtainedMarks.objects.bulk_create([
                ObtainedMarks(**v) for v in validated
            ])
            log_activity(
                request,
                action='create',
                entity_type='obtained marks',
                description=f"Added obtained marks for {len(objs)} records.",
                details={'count': len(objs)},
            )
            return Response(ObtainedMarksSerializer(objs, many=True).data, status=status.HTTP_201_CREATED)

        ser = ObtainedMarksSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        exam_data = ser.validated_data['exam_data']
        if not ExamData.objects.filter(pk=exam_data.id, institute=institute).exists():
            return Response({'detail': 'exam_data does not belong to your institute.'}, status=status.HTTP_403_FORBIDDEN)
        obj = ser.save()
        log_activity(
            request,
            action='create',
            entity_type='obtained marks',
            entity_id=obj.id,
            entity_name=str(obj.student_id),
            description=f"Added obtained marks for student #{obj.student_id}.",
            details={'student_id': obj.student_id, 'exam_data_id': obj.exam_data_id},
        )
        return Response(ObtainedMarksSerializer(obj).data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        return self._update_marks(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update_marks(request, pk, partial=True)

    def _update_marks(self, request, pk, partial):
        if getattr(request, '_verified_student', None):
            return Response({'detail': 'Students cannot write marks.'}, status=status.HTTP_403_FORBIDDEN)
        institute = request._verified_institute
        try:
            obj = ObtainedMarks.objects.select_related('exam_data').get(
                pk=pk, exam_data__institute=institute
            )
        except ObtainedMarks.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        ser = ObtainedMarksSerializer(obj, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        ser.save()
        log_activity(
            request,
            action='update',
            entity_type='obtained marks',
            entity_id=obj.id,
            entity_name=str(obj.student_id),
            description=f"Updated obtained marks for student #{obj.student_id}.",
            details={'student_id': obj.student_id, 'exam_data_id': obj.exam_data_id},
        )
        return Response(ObtainedMarksSerializer(obj).data)

    def delete(self, request, pk):
        if getattr(request, '_verified_student', None):
            return Response({'detail': 'Students cannot write marks.'}, status=status.HTTP_403_FORBIDDEN)
        institute = request._verified_institute
        try:
            obj = ObtainedMarks.objects.only('id', 'student_id', 'exam_data_id').get(pk=pk, exam_data__institute=institute)
        except ObtainedMarks.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        deleted_payload = {'entity_id': obj.id, 'student_id': obj.student_id, 'exam_data_id': obj.exam_data_id}
        obj.delete()
        log_activity(
            request,
            action='delete',
            entity_type='obtained marks',
            entity_id=deleted_payload['entity_id'],
            entity_name=str(deleted_payload['student_id']),
            description=f"Deleted obtained marks for student #{deleted_payload['student_id']}.",
            details={'student_id': deleted_payload['student_id'], 'exam_data_id': deleted_payload['exam_data_id']},
        )
        return Response({'detail': 'Deleted.'}, status=status.HTTP_200_OK)
