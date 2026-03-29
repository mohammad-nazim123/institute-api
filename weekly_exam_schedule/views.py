from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from institute_api.permissions import SchedulePermission

from .models import (
    ExamScheduleData,
    ExamScheduleDate,
    WeeklyScheduleData,
    WeeklyScheduleDay,
)
from .serializers import (
    ExamScheduleDateSerializer,
    WeeklyScheduleDaySerializer,
    build_schedule_dictionary,
    serialize_exam_entries,
    serialize_weekly_entries,
)


class WeeklyExamScheduleMixin:
    permission_classes = [SchedulePermission]

    def _hierarchy_values(self, request):
        body = request.data if hasattr(request, 'data') else {}
        return {
            'class_name': request.query_params.get('class_name') or body.get('class_name'),
            'branch': request.query_params.get('branch') or body.get('branch'),
            'academic_term': request.query_params.get('academic_term') or body.get('academic_term'),
        }

    def _require_hierarchy(self, request):
        hierarchy = self._hierarchy_values(request)
        missing = [key for key, value in hierarchy.items() if not value]
        if missing:
            raise ValidationError({
                field: ['This field is required.']
                for field in missing
            })
        return hierarchy

    def _weekly_queryset(self, institute, hierarchy):
        return WeeklyScheduleData.objects.select_related('weekly_schedule_day').filter(
            institute=institute,
            class_name=hierarchy['class_name'],
            branch=hierarchy['branch'],
            academic_term=hierarchy['academic_term'],
        ).order_by('weekly_schedule_day_id', 'id')

    def _exam_queryset(self, institute, hierarchy):
        return ExamScheduleData.objects.select_related('exam_schedule_date').filter(
            institute=institute,
            class_name=hierarchy['class_name'],
            branch=hierarchy['branch'],
            academic_term=hierarchy['academic_term'],
        ).order_by('exam_schedule_date_id', 'id')

    def _dictionary_payload(self, institute, hierarchy):
        weekly_schedule = serialize_weekly_entries(self._weekly_queryset(institute, hierarchy))
        exam_schedule = serialize_exam_entries(self._exam_queryset(institute, hierarchy))
        return build_schedule_dictionary(
            institute=institute,
            class_name=hierarchy['class_name'],
            branch=hierarchy['branch'],
            academic_term=hierarchy['academic_term'],
            weekly_schedule=weekly_schedule,
            exam_schedule=exam_schedule,
        )

    def _dictionary_response(self, institute, hierarchy):
        return Response(self._dictionary_payload(institute, hierarchy))

    def _hierarchy_from_child(self, child):
        return {
            'class_name': child.class_name,
            'branch': child.branch,
            'academic_term': child.academic_term,
        }

    def _entry_hierarchy(self, entry, request, child_relation_name):
        request_hierarchy = self._hierarchy_values(request)
        values = [request_hierarchy['class_name'], request_hierarchy['branch'], request_hierarchy['academic_term']]

        if any(values):
            if not all(values):
                raise ValidationError(
                    'class_name, branch, and academic_term must be provided together.'
                )
            return request_hierarchy

        prefetched_children = getattr(entry, '_prefetched_objects_cache', {}).get(child_relation_name)
        if prefetched_children is not None:
            child = prefetched_children[0] if prefetched_children else None
        else:
            child = getattr(entry, child_relation_name).only(
                'class_name',
                'branch',
                'academic_term',
            ).first()
        if child is None:
            raise ValidationError(
                'class_name, branch, and academic_term are required for this schedule item.'
            )
        return self._hierarchy_from_child(child)


class WeeklyExamScheduleDictionaryView(WeeklyExamScheduleMixin, APIView):
    def get(self, request):
        institute = request._verified_institute
        hierarchy = self._require_hierarchy(request)
        return self._dictionary_response(institute, hierarchy)


class BaseScheduleEntryView(WeeklyExamScheduleMixin, APIView):
    entry_model = None
    entry_serializer_class = None
    child_model = None
    child_relation_name = ''
    child_payload_key = ''

    def _entry_queryset(self, institute):
        return self.entry_model.objects.filter(institute=institute).only('id', 'institute_id')

    def _clean_payload(self, request):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        for key in ('institute', 'class_name', 'branch', 'academic_term'):
            data.pop(key, None)
        return data

    def _save_children(self, entry, items, hierarchy):
        getattr(entry, self.child_relation_name).all().delete()
        if not items:
            return

        self.child_model.objects.bulk_create([
            self.child_model(
                **{self.entry_fk_name: entry},
                institute=entry.institute,
                class_name=hierarchy['class_name'],
                branch=hierarchy['branch'],
                academic_term=hierarchy['academic_term'],
                **item,
            )
            for item in items
        ])

    def _save_entry(self, institute, serializer, hierarchy):
        validated_data = dict(serializer.validated_data)
        child_items = validated_data.pop(self.child_payload_key, None)

        entry = serializer.instance
        if entry is None:
            entry = self.entry_model.objects.create(institute=institute, **validated_data)
        else:
            changed_fields = list(validated_data.keys())
            for field, value in validated_data.items():
                setattr(entry, field, value)
            entry.institute = institute
            if changed_fields:
                changed_fields.append('institute')
            entry.save(update_fields=changed_fields if changed_fields else None)

        if child_items is not None:
            self._save_children(entry, child_items, hierarchy)
        return entry

    def get(self, request, pk=None):
        institute = request._verified_institute

        if pk is None:
            hierarchy = self._require_hierarchy(request)
            return self._dictionary_response(institute, hierarchy)

        try:
            entry = self._entry_queryset(institute).get(pk=pk)
        except self.entry_model.DoesNotExist:
            return Response({'detail': 'Schedule item not found.'}, status=status.HTTP_404_NOT_FOUND)

        hierarchy = self._entry_hierarchy(entry, request, self.child_relation_name)
        return self._dictionary_response(institute, hierarchy)

    def post(self, request):
        institute = request._verified_institute
        hierarchy = self._require_hierarchy(request)
        serializer = self.entry_serializer_class(data=self._clean_payload(request))
        serializer.is_valid(raise_exception=True)
        self._save_entry(institute, serializer, hierarchy)
        return self._dictionary_response(institute, hierarchy)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        institute = request._verified_institute
        try:
            entry = self._entry_queryset(institute).get(pk=pk)
        except self.entry_model.DoesNotExist:
            return Response({'detail': 'Schedule item not found.'}, status=status.HTTP_404_NOT_FOUND)

        hierarchy = self._entry_hierarchy(entry, request, self.child_relation_name)
        serializer = self.entry_serializer_class(
            entry,
            data=self._clean_payload(request),
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self._save_entry(institute, serializer, hierarchy)
        return self._dictionary_response(institute, hierarchy)

    def delete(self, request, pk):
        institute = request._verified_institute
        try:
            entry = self._entry_queryset(institute).get(pk=pk)
        except self.entry_model.DoesNotExist:
            return Response({'detail': 'Schedule item not found.'}, status=status.HTTP_404_NOT_FOUND)

        hierarchy = self._entry_hierarchy(entry, request, self.child_relation_name)
        entry.delete()
        return self._dictionary_response(institute, hierarchy)


class WeeklyScheduleEntryView(BaseScheduleEntryView):
    entry_model = WeeklyScheduleDay
    entry_serializer_class = WeeklyScheduleDaySerializer
    child_model = WeeklyScheduleData
    child_relation_name = 'weekly_schedule_data'
    child_payload_key = 'weekly_schedule_data'
    entry_fk_name = 'weekly_schedule_day'


class ExamScheduleEntryView(BaseScheduleEntryView):
    entry_model = ExamScheduleDate
    entry_serializer_class = ExamScheduleDateSerializer
    child_model = ExamScheduleData
    child_relation_name = 'exam_schedule_data'
    child_payload_key = 'exam_schedule_data'
    entry_fk_name = 'exam_schedule_date'
