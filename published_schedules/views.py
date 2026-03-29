import hashlib
import json

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from weekly_exam_schedule.models import ExamScheduleData, WeeklyScheduleData
from weekly_exam_schedule.serializers import serialize_exam_entries, serialize_weekly_entries

from .models import PublishedExamSchedule, PublishedWeeklySchedule
from .permissions import (
    PublishedScheduleAccessPermission,
    PublishedScheduleAdminKeyPermission,
)
from .serializers import (
    PublishedExamScheduleSerializer,
    PublishedWeeklyScheduleSerializer,
    build_exam_response,
    build_weekly_response,
)


ALREADY_EXISTS_MESSAGE = 'The data already exist.'


class PublishedSchedulesMixin:
    def _hierarchy_values(self, request):
        body = request.data if hasattr(request, 'data') else {}
        return {
            'class_name': request.query_params.get('class_name') or body.get('class_name'),
            'branch': request.query_params.get('branch') or body.get('branch'),
            'academic_term': request.query_params.get('academic_term') or body.get('academic_term'),
        }

    def _student_hierarchy(self, request):
        verified_student = getattr(request, '_verified_student', None)
        if verified_student is None:
            return None

        try:
            course_assignment = verified_student.course_assignments
        except ObjectDoesNotExist:
            return None

        hierarchy = {
            'class_name': course_assignment.class_name,
            'branch': course_assignment.branch,
            'academic_term': course_assignment.academic_term,
        }
        return hierarchy if all(hierarchy.values()) else None

    def _require_hierarchy(self, request):
        hierarchy = self._hierarchy_values(request)
        provided = [bool(value) for value in hierarchy.values()]

        if any(provided) and not all(provided):
            raise ValidationError(
                'class_name, branch, and academic_term must be provided together.'
            )

        student_hierarchy = self._student_hierarchy(request)
        if student_hierarchy:
            if all(provided) and hierarchy != student_hierarchy:
                raise PermissionDenied(
                    'Students can only access their own published schedule hierarchy.'
                )
            return student_hierarchy

        if all(provided):
            return hierarchy

        missing = [key for key, value in hierarchy.items() if not value]
        raise ValidationError({
            field: ['This field is required.']
            for field in missing
        })

    def _entry_hierarchy(self, request, entry):
        request_hierarchy = self._hierarchy_values(request)
        values = list(request_hierarchy.values())

        if any(values) and not all(values):
            raise ValidationError(
                'class_name, branch, and academic_term must be provided together.'
            )

        entry_hierarchy = {
            'class_name': entry.class_name,
            'branch': entry.branch,
            'academic_term': entry.academic_term,
        }

        student_hierarchy = self._student_hierarchy(request)
        if student_hierarchy:
            if entry_hierarchy != student_hierarchy:
                raise PermissionDenied(
                    'Students can only access their own published schedule hierarchy.'
                )
            if all(values) and request_hierarchy != student_hierarchy:
                raise PermissionDenied(
                    'Students can only access their own published schedule hierarchy.'
                )
            return student_hierarchy

        if all(values):
            return request_hierarchy

        return entry_hierarchy

    def _schedule_hash(self, schedule_data):
        return hashlib.sha256(
            json.dumps(schedule_data, sort_keys=True).encode('utf-8')
        ).hexdigest()

    def _source_weekly_schedule(self, institute, hierarchy):
        queryset = WeeklyScheduleData.objects.select_related('weekly_schedule_day').filter(
            institute=institute,
            class_name=hierarchy['class_name'],
            branch=hierarchy['branch'],
            academic_term=hierarchy['academic_term'],
        ).order_by('weekly_schedule_day_id', 'id')
        return serialize_weekly_entries(queryset)

    def _source_exam_schedule(self, institute, hierarchy):
        queryset = ExamScheduleData.objects.select_related('exam_schedule_date').filter(
            institute=institute,
            class_name=hierarchy['class_name'],
            branch=hierarchy['branch'],
            academic_term=hierarchy['academic_term'],
        ).order_by('exam_schedule_date_id', 'id')
        return serialize_exam_entries(queryset)


class BasePublishedScheduleView(PublishedSchedulesMixin, APIView):
    model = None
    serializer_class = None
    schedule_key = ''

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [PublishedScheduleAccessPermission()]
        return [PublishedScheduleAdminKeyPermission()]

    def _build_response(self, institute, hierarchy, schedule_data, **extra):
        raise NotImplementedError

    def _schedule_from_validated_data(self, validated_data):
        return validated_data.pop('schedule_data', None)

    def get(self, request, pk=None):
        institute = request._verified_institute

        if pk is None:
            hierarchy = self._require_hierarchy(request)
            entry = self.model.objects.filter(
                institute=institute,
                class_name=hierarchy['class_name'],
                branch=hierarchy['branch'],
                academic_term=hierarchy['academic_term'],
            ).first()
            schedule_data = entry.schedule_data if entry else []
            return Response(
                self._build_response(
                    institute,
                    hierarchy,
                    schedule_data,
                    published_id=entry.id if entry else None,
                )
            )

        try:
            entry = self.model.objects.get(pk=pk, institute=institute)
        except self.model.DoesNotExist:
            return Response({'detail': 'Published schedule not found.'}, status=status.HTTP_404_NOT_FOUND)

        hierarchy = self._entry_hierarchy(request, entry)
        return Response(
            self._build_response(
                institute,
                hierarchy,
                entry.schedule_data,
                published_id=entry.id,
            )
        )

    def post(self, request):
        institute = request._verified_institute
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = dict(serializer.validated_data)
        schedule_data = self._schedule_from_validated_data(validated_data)
        hierarchy = {
            'class_name': validated_data['class_name'],
            'branch': validated_data['branch'],
            'academic_term': validated_data['academic_term'],
        }

        if self.model.objects.filter(institute=institute, **hierarchy).exists():
            return Response(
                {'detail': 'Published schedule already exists for this hierarchy.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        entry = self.model.objects.create(
            institute=institute,
            schedule_data=schedule_data or [],
            source_hash=self._schedule_hash(schedule_data or []),
            published_at=now,
            updated_at=now,
            **hierarchy,
        )
        return Response(
            self._build_response(
                institute,
                hierarchy,
                entry.schedule_data,
                published_id=entry.id,
                message='Published schedule created successfully.',
            )
        )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        institute = request._verified_institute

        try:
            entry = self.model.objects.get(pk=pk, institute=institute)
        except self.model.DoesNotExist:
            return Response({'detail': 'Published schedule not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(entry, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        validated_data = dict(serializer.validated_data)
        schedule_data = self._schedule_from_validated_data(validated_data)

        if 'class_name' in validated_data:
            entry.class_name = validated_data['class_name']
        if 'branch' in validated_data:
            entry.branch = validated_data['branch']
        if 'academic_term' in validated_data:
            entry.academic_term = validated_data['academic_term']
        if schedule_data is not None:
            entry.schedule_data = schedule_data
            entry.source_hash = self._schedule_hash(schedule_data)

        entry.updated_at = timezone.now()
        entry.save()

        hierarchy = {
            'class_name': entry.class_name,
            'branch': entry.branch,
            'academic_term': entry.academic_term,
        }
        return Response(
            self._build_response(
                institute,
                hierarchy,
                entry.schedule_data,
                published_id=entry.id,
                message='Published schedule updated successfully.',
            )
        )

    def delete(self, request, pk):
        institute = request._verified_institute

        try:
            entry = self.model.objects.get(pk=pk, institute=institute)
        except self.model.DoesNotExist:
            return Response({'detail': 'Published schedule not found.'}, status=status.HTTP_404_NOT_FOUND)

        hierarchy = {
            'class_name': entry.class_name,
            'branch': entry.branch,
            'academic_term': entry.academic_term,
        }
        entry.delete()

        return Response(
            self._build_response(
                institute,
                hierarchy,
                [],
                published_id=entry.id,
                message='Published schedule deleted successfully.',
            )
        )


class PublishedWeeklyScheduleView(BasePublishedScheduleView):
    model = PublishedWeeklySchedule
    serializer_class = PublishedWeeklyScheduleSerializer
    schedule_key = 'weekly_schedule'

    def _build_response(self, institute, hierarchy, schedule_data, **extra):
        return build_weekly_response(institute, hierarchy, schedule_data, **extra)


class PublishedExamScheduleView(BasePublishedScheduleView):
    model = PublishedExamSchedule
    serializer_class = PublishedExamScheduleSerializer
    schedule_key = 'exam_schedule'

    def _build_response(self, institute, hierarchy, schedule_data, **extra):
        return build_exam_response(institute, hierarchy, schedule_data, **extra)


class PublishedWeeklySchedulePublishView(PublishedSchedulesMixin, APIView):
    permission_classes = [PublishedScheduleAdminKeyPermission]

    def post(self, request):
        institute = request._verified_institute
        hierarchy = self._require_hierarchy(request)
        source_data = self._source_weekly_schedule(institute, hierarchy)
        source_hash = self._schedule_hash(source_data)
        now = timezone.now()

        entry = PublishedWeeklySchedule.objects.filter(
            institute=institute,
            class_name=hierarchy['class_name'],
            branch=hierarchy['branch'],
            academic_term=hierarchy['academic_term'],
        ).first()

        if entry is None:
            if not source_data:
                return Response(
                    build_weekly_response(
                        institute,
                        hierarchy,
                        [],
                        published_id=None,
                        message='No weekly schedule found for the selected hierarchy.',
                    )
                )

            entry = PublishedWeeklySchedule.objects.create(
                institute=institute,
                class_name=hierarchy['class_name'],
                branch=hierarchy['branch'],
                academic_term=hierarchy['academic_term'],
                schedule_data=source_data,
                source_hash=source_hash,
                published_at=now,
                updated_at=now,
            )
            return Response(
                build_weekly_response(
                    institute,
                    hierarchy,
                    entry.schedule_data,
                    published_id=entry.id,
                    action='created',
                    message='Published weekly schedule created successfully.',
                )
            )

        if entry.source_hash == source_hash and entry.schedule_data == source_data:
            return Response(
                build_weekly_response(
                    institute,
                    hierarchy,
                    entry.schedule_data,
                    published_id=entry.id,
                    message=ALREADY_EXISTS_MESSAGE,
                )
            )

        entry.schedule_data = source_data
        entry.source_hash = source_hash
        entry.updated_at = now
        entry.save(update_fields=['schedule_data', 'source_hash', 'updated_at'])

        return Response(
            build_weekly_response(
                institute,
                hierarchy,
                entry.schedule_data,
                published_id=entry.id,
                action='updated',
                message='Published weekly schedule updated successfully.',
            )
        )


class PublishedExamSchedulePublishView(PublishedSchedulesMixin, APIView):
    permission_classes = [PublishedScheduleAdminKeyPermission]

    def post(self, request):
        institute = request._verified_institute
        hierarchy = self._require_hierarchy(request)
        source_data = self._source_exam_schedule(institute, hierarchy)
        source_hash = self._schedule_hash(source_data)
        now = timezone.now()

        entry = PublishedExamSchedule.objects.filter(
            institute=institute,
            class_name=hierarchy['class_name'],
            branch=hierarchy['branch'],
            academic_term=hierarchy['academic_term'],
        ).first()

        if entry is None:
            if not source_data:
                return Response(
                    build_exam_response(
                        institute,
                        hierarchy,
                        [],
                        published_id=None,
                        message='No exam schedule found for the selected hierarchy.',
                    )
                )

            entry = PublishedExamSchedule.objects.create(
                institute=institute,
                class_name=hierarchy['class_name'],
                branch=hierarchy['branch'],
                academic_term=hierarchy['academic_term'],
                schedule_data=source_data,
                source_hash=source_hash,
                published_at=now,
                updated_at=now,
            )
            return Response(
                build_exam_response(
                    institute,
                    hierarchy,
                    entry.schedule_data,
                    published_id=entry.id,
                    action='created',
                    message='Published exam schedule created successfully.',
                )
            )

        if entry.source_hash == source_hash and entry.schedule_data == source_data:
            return Response(
                build_exam_response(
                    institute,
                    hierarchy,
                    entry.schedule_data,
                    published_id=entry.id,
                    message=ALREADY_EXISTS_MESSAGE,
                )
            )

        entry.schedule_data = source_data
        entry.source_hash = source_hash
        entry.updated_at = now
        entry.save(update_fields=['schedule_data', 'source_hash', 'updated_at'])

        return Response(
            build_exam_response(
                institute,
                hierarchy,
                entry.schedule_data,
                published_id=entry.id,
                action='updated',
                message='Published exam schedule updated successfully.',
            )
        )
