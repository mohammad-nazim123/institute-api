from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from institute_api.permissions import AttendancePermission
from students.models import Student
from .models import Attendance
from .serializers import StudentSerializer, MarkAttendanceSerializer, AttendanceSerializer


class StudentListView(APIView):
    """
    GET /api/students/?institute=<id>
    Returns all students belonging to the verified institute.
    Requires X-Admin-Key (32-char) or X-Personal-Key (professor's 15-digit ID).
    """
    permission_classes = [AttendancePermission]

    def get(self, request):
        institute = request._verified_institute
        students = Student.objects.filter(institute=institute)
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MarkAttendanceView(APIView):
    """
    POST /api/attendance/mark/?institute=<id>
    Bulk create/update attendance for the given date.
    Requires X-Admin-Key (32-char) or X-Personal-Key (professor's 15-digit ID).
    """
    permission_classes = [AttendancePermission]

    def post(self, request):
        serializer = MarkAttendanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        date = serializer.validated_data['date']
        records = serializer.validated_data['attendance']

        # The professor who marked attendance (may be None for admin-key access)
        marked_by = getattr(request, '_verified_professor', None)

        results = []
        errors = []

        for record in records:
            student_id = record['student_id']
            try:
                student = Student.objects.get(pk=student_id)
            except Student.DoesNotExist:
                errors.append({'student_id': student_id, 'error': 'Student not found.'})
                continue

            obj, created = Attendance.objects.update_or_create(
                student=student,
                date=date,
                defaults={
                    'status': record['status'],
                    'class_name': record.get('class_name', ''),
                    'branch': record.get('branch', ''),
                    'year_semester': record.get('year_semester', ''),
                    'marked_by': marked_by,
                },
            )
            results.append({
                'student_id': student_id,
                'student_name': student.name,
                'date': str(date),
                'class_name': obj.class_name,
                'branch': obj.branch,
                'year_semester': obj.year_semester,
                'status': obj.status,
                'action': 'created' if created else 'updated',
            })

        response_data = {'results': results}
        if errors:
            response_data['errors'] = errors

        http_status = status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        return Response(response_data, status=http_status)


class StudentAttendanceView(APIView):
    """
    GET /api/attendance/student/<student_id>/?institute=<id>&date=YYYY-MM-DD&month=YYYY-MM
    Returns attendance records for a specific student.
    Can filter by specific 'date' or a whole 'month'.
    Requires X-Admin-Key or X-Personal-Key.
    """
    permission_classes = [AttendancePermission]

    def get(self, request, student_id):
        institute = request._verified_institute

        try:
            student = Student.objects.get(pk=student_id, institute=institute)
        except Student.DoesNotExist:
            return Response(
                {'detail': 'Student not found in this institute.'},
                status=status.HTTP_404_NOT_FOUND
            )

        queryset = Attendance.objects.filter(student=student).order_by('-date')

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
