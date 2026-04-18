from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from activity_feed.services import ActivityLogMixin, log_activity
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    STUDENT_ACCESS_CONTROL,
    AttendancePermission,
)
from iinstitutes_list.academic_terms import (
    canonicalize_institute_academic_term,
    filter_queryset_by_academic_term,
)
from students.models import Student
from .models import Attendance, AttendanceSubmission
from .serializers import (
    AttendanceSerializer,
    MarkAttendanceSerializer,
    StudentAttendanceListSerializer,
    StudentAttendanceSummarySerializer,
)


def parse_student_ids(raw_ids):
    raw_ids = str(raw_ids or '').strip()
    if not raw_ids:
        return None

    try:
        return [int(value.strip()) for value in raw_ids.split(',') if value.strip()]
    except ValueError as exc:
        raise ValueError('Invalid student_ids format. Use comma-separated numeric ids.') from exc


def apply_attendance_period_filters(queryset, request):
    date_param = (request.query_params.get('date') or '').strip()
    month_param = (request.query_params.get('month') or '').strip()
    year_param = (request.query_params.get('year') or '').strip()

    if date_param:
        return queryset.filter(submission__date=date_param)

    if month_param:
        try:
            year, month = month_param.split('-')
            return queryset.filter(submission__date__year=year, submission__date__month=month)
        except ValueError as exc:
            raise ValueError('Invalid month format. Please use YYYY-MM.') from exc

    if year_param:
        try:
            year_value = int(year_param)
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid year format. Please use YYYY.') from exc
        return queryset.filter(submission__date__year=year_value)

    return queryset


def format_attendance_student_result(attendance):
    return {
        'id': attendance.id,
        'student_id': attendance.student_id,
        'status': attendance.status,
    }


def format_attendance_submission_payload(submission, attendances):
    marked_by = submission.marked_by
    return {
        'id': submission.id,
        'institute_id': submission.institute_id,
        'class_name': submission.class_name,
        'branch': submission.branch,
        'year_semester': submission.year_semester,
        'marked_by': marked_by.name if marked_by else None,
        'marked_by_id': marked_by.id if marked_by else None,
        'attendance_time': (
            submission.attendance_time.isoformat()
            if submission.attendance_time else None
        ),
        'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
        'date': str(submission.date),
        'student_result': [
            format_attendance_student_result(attendance)
            for attendance in attendances
        ],
    }


def format_grouped_attendance_payload(attendances):
    grouped = {}

    for attendance in attendances:
        submission_id = attendance.submission_id
        if submission_id not in grouped:
            grouped[submission_id] = {
                'submission': attendance.submission,
                'attendances': [],
            }
        grouped[submission_id]['attendances'].append(attendance)

    return [
        format_attendance_submission_payload(group['submission'], group['attendances'])
        for group in grouped.values()
    ]


class StudentListView(APIView):
    """
    GET /attendance/students/?institute=<id>
    Returns all students belonging to the verified institute.
    """
    permission_classes = [AttendancePermission]
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def get(self, request):
        institute = request._verified_institute
        queryset = Student.objects.filter(institute=institute).order_by('id')

        search = (request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(name__icontains=search)

        class_name = (request.query_params.get('class_name') or '').strip()
        branch = (request.query_params.get('branch') or '').strip()
        academic_term = canonicalize_institute_academic_term(
            institute,
            (request.query_params.get('academic_term') or '').strip(),
        )

        if class_name:
            queryset = queryset.filter(course_assignments__class_name__iexact=class_name)
        if branch:
            queryset = queryset.filter(course_assignments__branch__iexact=branch)
        if academic_term:
            queryset = filter_queryset_by_academic_term(
                queryset,
                'course_assignments__academic_term',
                academic_term,
                institute,
            )

        students = list(queryset.values('id', 'name', 'gender', 'category'))
        return Response(students, status=status.HTTP_200_OK)


class StudentAttendanceBulkView(APIView):
    """
    GET /attendance/students/attendance/?institute=<id>&date=YYYY-MM-DD&student_ids=1,2,3
    Returns many students and their attendance records in one response.
    """
    permission_classes = [AttendancePermission]
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def _parse_student_ids(self, request):
        return parse_student_ids(request.query_params.get('student_ids'))

    def get(self, request):
        institute = request._verified_institute
        date_param = request.query_params.get('date')
        month_param = request.query_params.get('month')

        if not date_param and not month_param:
            return Response(
                {'detail': 'Provide either date=YYYY-MM-DD or month=YYYY-MM.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if date_param and month_param:
            return Response(
                {'detail': 'Provide either date or month, not both.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student_ids = self._parse_student_ids(request)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        students = Student.objects.filter(institute=institute).only(
            'id',
            'name',
            'gender',
            'category',
        ).order_by('id')
        if student_ids is not None:
            students = students.filter(pk__in=student_ids)

        attendance_queryset = (
            Attendance.objects
            .select_related('submission', 'submission__marked_by')
            .filter(submission__institute=institute)
            .order_by('-submission__date')
        )
        if date_param:
            attendance_queryset = attendance_queryset.filter(submission__date=date_param)
        else:
            try:
                year, month = month_param.split('-')
                attendance_queryset = attendance_queryset.filter(
                    submission__date__year=year,
                    submission__date__month=month,
                )
            except ValueError:
                return Response(
                    {'detail': 'Invalid month format. Please use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if student_ids is not None:
            attendance_queryset = attendance_queryset.filter(student_id__in=student_ids)

        students = students.prefetch_related(
            Prefetch('attendances', queryset=attendance_queryset)
        )

        serializer = StudentAttendanceListSerializer(students, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentAttendanceSummaryView(APIView):
    """
    GET /attendance/students/summary/?institute=<id>&month=YYYY-MM&student_ids=1,2,3
    Returns aggregated attendance counts per student without sending daily records.
    """
    permission_classes = [AttendancePermission]
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def get(self, request):
        institute = request._verified_institute
        date_param = request.query_params.get('date')
        month_param = request.query_params.get('month')
        year_param = request.query_params.get('year')

        provided_periods = [bool(date_param), bool(month_param), bool(year_param)]
        if sum(provided_periods) != 1:
            return Response(
                {'detail': 'Provide exactly one of date=YYYY-MM-DD, month=YYYY-MM, or year=YYYY.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student_ids = parse_student_ids(request.query_params.get('student_ids'))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        students = Student.objects.filter(institute=institute).only('id').order_by('id')
        if student_ids is not None:
            students = students.filter(pk__in=student_ids)

        student_id_list = list(students.values_list('id', flat=True))
        if not student_id_list:
            return Response([], status=status.HTTP_200_OK)

        attendance_queryset = Attendance.objects.filter(
            student_id__in=student_id_list,
            submission__institute=institute,
        )
        if date_param:
            attendance_queryset = attendance_queryset.filter(submission__date=date_param)
        elif month_param:
            try:
                year, month = month_param.split('-')
                attendance_queryset = attendance_queryset.filter(
                    submission__date__year=year,
                    submission__date__month=month,
                )
            except ValueError:
                return Response(
                    {'detail': 'Invalid month format. Please use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            try:
                year_value = int(year_param)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'Invalid year format. Please use YYYY.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            attendance_queryset = attendance_queryset.filter(submission__date__year=year_value)

        aggregated = attendance_queryset.values('student_id').annotate(
            present=Count('id', filter=Q(status=True)),
            absent=Count('id', filter=Q(status=False)),
        )

        stats_by_student_id = {
            row['student_id']: {
                'present': row['present'],
                'absent': row['absent'],
            }
            for row in aggregated
        }

        payload = []
        for student_id in student_id_list:
            stats = stats_by_student_id.get(student_id, {'present': 0, 'absent': 0})
            total = stats['present'] + stats['absent']
            payload.append({
                'student_id': student_id,
                'present': stats['present'],
                'absent': stats['absent'],
                'total': total,
                'percentage': round((stats['present'] / total) * 100) if total > 0 else 0,
            })

        serializer = StudentAttendanceSummarySerializer(payload, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AttendanceListCreateView(ActivityLogMixin, generics.ListCreateAPIView):
    """
    GET/POST /attendance/attendance/records/?institute=<id>
    Lists or creates individual student attendance records.
    """
    activity_entity_type = 'student attendance'
    activity_name_field = 'student.name'
    permission_classes = [AttendancePermission]
    serializer_class = AttendanceSerializer
    pagination_class = None
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def get_queryset(self):
        queryset = (
            Attendance.objects
            .select_related('student', 'submission', 'submission__marked_by')
            .filter(
                student__institute=self.request._verified_institute,
                submission__institute=self.request._verified_institute,
            )
            .order_by('-submission__date', 'id')
        )

        student_id = (
            self.request.query_params.get('student')
            or self.request.query_params.get('student_id')
        )
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        try:
            student_ids = parse_student_ids(self.request.query_params.get('student_ids'))
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        if student_ids is not None:
            queryset = queryset.filter(student_id__in=student_ids)

        class_name = (self.request.query_params.get('class_name') or '').strip()
        branch = (self.request.query_params.get('branch') or '').strip()
        academic_term = canonicalize_institute_academic_term(
            self.request._verified_institute,
            (
                self.request.query_params.get('academic_term')
                or self.request.query_params.get('year_semester')
                or ''
            ).strip(),
        )

        if class_name:
            queryset = queryset.filter(submission__class_name__iexact=class_name)
        if branch:
            queryset = queryset.filter(submission__branch__iexact=branch)
        if academic_term:
            queryset = queryset.filter(submission__year_semester__iexact=academic_term)

        try:
            return apply_attendance_period_filters(queryset, self.request)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        context['marked_by'] = getattr(self.request, '_verified_professor', None)
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        return Response(
            format_grouped_attendance_payload(queryset),
            status=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            format_attendance_submission_payload(
                serializer.instance.submission,
                [serializer.instance],
            ),
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class AttendanceDetailView(ActivityLogMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/PUT/DELETE /attendance/attendance/records/<id>/?institute=<id>
    Manages one student attendance record.
    """
    activity_entity_type = 'student attendance'
    activity_name_field = 'student.name'
    permission_classes = [AttendancePermission]
    serializer_class = AttendanceSerializer
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def get_queryset(self):
        return (
            Attendance.objects
            .select_related('student', 'submission', 'submission__marked_by')
            .filter(
                student__institute=self.request._verified_institute,
                submission__institute=self.request._verified_institute,
            )
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        context['marked_by'] = getattr(self.request, '_verified_professor', None)
        return context

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(
            format_attendance_submission_payload(instance.submission, [instance]),
            status=status.HTTP_200_OK,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(
            format_attendance_submission_payload(
                serializer.instance.submission,
                [serializer.instance],
            ),
            status=status.HTTP_200_OK,
        )

    def perform_update(self, serializer):
        submitted_at = timezone.now()
        save_kwargs = {
            'submitted_at': submitted_at,
            'attendance_time': AttendanceSubmission.derive_attendance_time(submitted_at),
        }
        marked_by = getattr(self.request, '_verified_professor', None)
        if marked_by is not None:
            save_kwargs['marked_by'] = marked_by

        serializer.save(**save_kwargs)
        self.log_instance_activity('update', serializer.instance)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        response_data = format_attendance_submission_payload(
            instance.submission,
            [instance],
        )
        self.perform_destroy(instance)
        return Response(response_data, status=status.HTTP_200_OK)


class MarkAttendanceView(APIView):
    """
    POST /attendance/mark/?institute=<id>
    Bulk create/update attendance for the given date.

    OPTIMIZED:
    - Pre-fetches all students in 1 query instead of 1-per-student
    - Uses bulk_create + update_fields for existing records (2 queries total)
    - Uses update_or_create for individual records with a students map
    """
    permission_classes = [AttendancePermission]
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def post(self, request):
        serializer = MarkAttendanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        date = serializer.validated_data['date']
        records = serializer.validated_data['attendance']
        marked_by = getattr(request, '_verified_professor', None)
        submitted_at = timezone.now()
        attendance_time = AttendanceSubmission.derive_attendance_time(submitted_at)
        first_record = records[0]
        class_name = serializer.validated_data.get('class_name') or first_record.get('class_name', '')
        branch = serializer.validated_data.get('branch') or first_record.get('branch', '')
        year_semester = serializer.validated_data.get('year_semester') or first_record.get('year_semester', '')
        normalized_year_semester = canonicalize_institute_academic_term(
            request._verified_institute,
            year_semester,
        )
        submission, _created = AttendanceSubmission.objects.update_or_create(
            institute=request._verified_institute,
            date=date,
            class_name=class_name,
            branch=branch,
            year_semester=normalized_year_semester,
            defaults={
                'marked_by': marked_by,
                'submitted_at': submitted_at,
                'attendance_time': attendance_time,
            },
        )

        # ── 1. Fetch all needed students in ONE query ──────────────────────────
        student_ids = [r['student_id'] for r in records]
        students_map = {
            s.id: s
            for s in Student.objects.filter(pk__in=student_ids).only('id', 'name')
        }

        # ── 2. Fetch existing attendance rows for this date in ONE query ───────
        existing_map = {
            a.student_id: a
            for a in Attendance.objects.filter(
                student_id__in=student_ids,
                submission__institute=request._verified_institute,
                submission__date=date,
            ).select_related('submission')
        }

        results = []
        errors = []
        to_create = []
        to_update = []

        for record in records:
            sid = record['student_id']
            student = students_map.get(sid)

            if student is None:
                errors.append({'student_id': sid, 'error': 'Student not found.'})
                continue

            existing = existing_map.get(sid)

            if existing:
                # Update in-memory; bulk_update below
                existing.status = record['status']
                existing.submission = submission
                to_update.append(existing)
                action = 'updated'
            else:
                to_create.append(Attendance(
                    student=student,
                    submission=submission,
                    status=record['status'],
                ))
                action = 'created'

            results.append({
                'student_id': sid,
                'student_name': student.name,
                'date': str(date),
                'class_name': submission.class_name,
                'branch': submission.branch,
                'year_semester': normalized_year_semester,
                'status': record['status'],
                'attendance_time': attendance_time.isoformat(),
                'submitted_at': submitted_at.isoformat(),
                'action': action,
            })

        # ── 3. Bulk create new rows (1 query) ──────────────────────────────────
        if to_create:
            Attendance.objects.bulk_create(to_create, ignore_conflicts=True)

        # ── 4. Bulk update existing rows (1 query) ─────────────────────────────
        if to_update:
            Attendance.objects.bulk_update(
                to_update,
                ['status', 'submission'],
            )

        saved_records_by_student_id = {
            attendance.student_id: attendance
            for attendance in Attendance.objects.filter(
                student_id__in=student_ids,
                submission=submission,
            ).only('id', 'student_id')
        }
        for item in results:
            saved_record = saved_records_by_student_id.get(item['student_id'])
            if saved_record:
                item['id'] = saved_record.id

        if results:
            first_result = results[0]
            created_count = sum(1 for item in results if item['action'] == 'created')
            updated_count = sum(1 for item in results if item['action'] == 'updated')
            present_count = sum(1 for item in results if item.get('status') is True)
            absent_count = sum(1 for item in results if item.get('status') is False)

            log_activity(
                request,
                action='mark',
                entity_type='student attendance',
                description=(
                    f"Attendance was submitted for {len(results)} students on {first_result['date']}."
                ),
                details={
                    'date': first_result['date'],
                    'class_name': first_result['class_name'],
                    'branch': first_result['branch'],
                    'year_semester': first_result['year_semester'],
                    'submitted_students': len(results),
                    'present_count': present_count,
                    'absent_count': absent_count,
                    'created_count': created_count,
                    'updated_count': updated_count,
                    'error_count': len(errors),
                },
            )

        saved_records = [
            saved_records_by_student_id[item['student_id']]
            for item in results
            if item['student_id'] in saved_records_by_student_id
        ]
        response_data = format_attendance_submission_payload(submission, saved_records)
        if errors:
            response_data['errors'] = errors

        http_status = status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        return Response(response_data, status=http_status)


class StudentAttendanceView(APIView):
    """
    GET /attendance/student/<student_id>/?institute=<id>&date=YYYY-MM-DD&month=YYYY-MM
    Returns attendance records for a specific student.
    """
    permission_classes = [AttendancePermission]
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def get(self, request, student_id):
        institute = request._verified_institute

        try:
            student = Student.objects.only('id', 'name').get(pk=student_id, institute=institute)
        except Student.DoesNotExist:
            return Response(
                {'detail': 'Student not found in this institute.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # select_related marked_by so the serializer doesn't hit professor table per row
        queryset = (
            Attendance.objects
            .select_related('student', 'submission', 'submission__marked_by')
            .filter(student=student, submission__institute=institute)
            .order_by('-submission__date')
        )

        date_param = request.query_params.get('date')
        month_param = request.query_params.get('month')

        if date_param:
            queryset = queryset.filter(submission__date=date_param)
        elif month_param:
            try:
                year, month = month_param.split('-')
                queryset = queryset.filter(
                    submission__date__year=year,
                    submission__date__month=month,
                )
            except ValueError:
                return Response(
                    {'detail': 'Invalid month format. Please use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = AttendanceSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
