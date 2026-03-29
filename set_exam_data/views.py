from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from institute_api.permissions import SchedulePermission
from students.models import Student

from .models import ExamData, ObtainedMarks
from .serializers import ExamDataItemSerializer, ExamDictionarySerializer, ObtainedMarksSerializer


class ExamDataMixin:
    """Shared helpers for hierarchy resolution and dictionary response."""
    permission_classes = [SchedulePermission]

    def _hierarchy(self, request):
        body = request.data if hasattr(request, 'data') else {}
        return {
            'class_name': request.query_params.get('class_name') or body.get('class_name') or body.get('class'),
            'branch':     request.query_params.get('branch')     or body.get('branch'),
            'academic_term': request.query_params.get('academic_term') or body.get('academic_term') or body.get('academic_terms'),
        }

    def _require_hierarchy(self, request):
        h = self._hierarchy(request)
        missing = [k for k, v in h.items() if not v]
        if missing:
            raise ValidationError({f: ['This field is required.'] for f in missing})
        return h

    def _queryset(self, institute, h):
        return (
            ExamData.objects
            .filter(
                institute=institute,
                class_name=h['class_name'],
                branch=h['branch'],
                academic_term=h['academic_term'],
            )
            .order_by('id')
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
            ExamData.objects.bulk_create(items)
        else:
            ser = ExamDataItemSerializer(data=payload)
            ser.is_valid(raise_exception=True)
            ExamData.objects.create(
                institute=institute,
                class_name=h['class_name'],
                branch=h['branch'],
                academic_term=h['academic_term'],
                **ser.validated_data,
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
        entry.delete()
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
            ('academic_term', 'exam_data__academic_term'),
            ('student',       'student_id'),
            ('exam_data',     'exam_data_id'),
        ]:
            val = request.query_params.get(param)
            if val:
                qs = qs.filter(**{lookup: val})
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
            return Response(ObtainedMarksSerializer(objs, many=True).data, status=status.HTTP_201_CREATED)

        ser = ObtainedMarksSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        exam_data = ser.validated_data['exam_data']
        if not ExamData.objects.filter(pk=exam_data.id, institute=institute).exists():
            return Response({'detail': 'exam_data does not belong to your institute.'}, status=status.HTTP_403_FORBIDDEN)
        obj = ser.save()
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
        return Response(ObtainedMarksSerializer(obj).data)

    def delete(self, request, pk):
        if getattr(request, '_verified_student', None):
            return Response({'detail': 'Students cannot write marks.'}, status=status.HTTP_403_FORBIDDEN)
        institute = request._verified_institute
        try:
            obj = ObtainedMarks.objects.only('id').get(pk=pk, exam_data__institute=institute)
        except ObtainedMarks.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({'detail': 'Deleted.'}, status=status.HTTP_200_OK)
