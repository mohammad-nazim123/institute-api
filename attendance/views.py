from django.db.models import Count, Prefetch, Q

from activity_feed.services import log_activity
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
from .models import Attendance
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

        attendance_queryset = Attendance.objects.select_related('marked_by').order_by('-date')
        if date_param:
            attendance_queryset = attendance_queryset.filter(date=date_param)
        else:
            try:
                year, month = month_param.split('-')
                attendance_queryset = attendance_queryset.filter(date__year=year, date__month=month)
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

        attendance_queryset = Attendance.objects.filter(student_id__in=student_id_list)
        if date_param:
            attendance_queryset = attendance_queryset.filter(date=date_param)
        elif month_param:
            try:
                year, month = month_param.split('-')
                attendance_queryset = attendance_queryset.filter(date__year=year, date__month=month)
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
            attendance_queryset = attendance_queryset.filter(date__year=year_value)

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

        # ── 1. Fetch all needed students in ONE query ──────────────────────────
        student_ids = [r['student_id'] for r in records]
        students_map = {
            s.id: s
            for s in Student.objects.filter(pk__in=student_ids).only('id', 'name')
        }

        # ── 2. Fetch existing attendance rows for this date in ONE query ───────
        existing_map = {
            a.student_id: a
            for a in Attendance.objects.filter(student_id__in=student_ids, date=date)
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

            normalized_year_semester = canonicalize_institute_academic_term(
                request._verified_institute,
                record.get('year_semester', ''),
            )

            if existing:
                # Update in-memory; bulk_update below
                existing.status = record['status']
                existing.class_name = record.get('class_name', existing.class_name)
                existing.branch = record.get('branch', existing.branch)
                existing.year_semester = normalized_year_semester or existing.year_semester
                existing.marked_by = marked_by
                to_update.append(existing)
                action = 'updated'
            else:
                to_create.append(Attendance(
                    student=student,
                    date=date,
                    status=record['status'],
                    class_name=record.get('class_name', ''),
                    branch=record.get('branch', ''),
                    year_semester=normalized_year_semester,
                    marked_by=marked_by,
                ))
                action = 'created'

            results.append({
                'student_id': sid,
                'student_name': student.name,
                'date': str(date),
                'class_name': record.get('class_name', ''),
                'branch': record.get('branch', ''),
                'year_semester': normalized_year_semester,
                'status': record['status'],
                'action': action,
            })

        # ── 3. Bulk create new rows (1 query) ──────────────────────────────────
        if to_create:
            Attendance.objects.bulk_create(to_create, ignore_conflicts=True)

        # ── 4. Bulk update existing rows (1 query) ─────────────────────────────
        if to_update:
            Attendance.objects.bulk_update(
                to_update,
                ['status', 'class_name', 'branch', 'year_semester', 'marked_by'],
            )

        if results:
            first_result = results[0]
            created_count = sum(1 for item in results if item['action'] == 'created')
            updated_count = sum(1 for item in results if item['action'] == 'updated')
            present_count = sum(1 for item in results if str(item.get('status', '')).lower() == 'present')
            absent_count = sum(1 for item in results if str(item.get('status', '')).lower() == 'absent')

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

        response_data = {'results': results}
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
            .select_related('student', 'marked_by')
            .filter(student=student)
            .order_by('-date')
        )

        date_param = request.query_params.get('date')
        month_param = request.query_params.get('month')

        if date_param:
            queryset = queryset.filter(date=date_param)
        elif month_param:
            try:
                year, month = month_param.split('-')
                queryset = queryset.filter(date__year=year, date__month=month)
            except ValueError:
                return Response(
                    {'detail': 'Invalid month format. Please use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = AttendanceSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
