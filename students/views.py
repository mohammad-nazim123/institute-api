from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from .models import Student, StudentCourseDetails, SubjectsAssigned
from rest_framework.views import APIView
from .serializers import StudentSerializer, CourseSerializer, StudentIdLookUpSerializer, SubjectsAssignedSerializer
from rest_framework.response import Response
from rest_framework import status
from institute_api.mixins import InstituteDictResponseMixin
from institute_api.permissions import InstituteKeyPermission, PersonalKeyPermission, AttendancePermission
from iinstitutes_list.models import Institute


class StudentViewSet(InstituteDictResponseMixin, ModelViewSet):
    serializer_class = StudentSerializer
    entity_key = 'students'
    entity_name_field = 'name'

    def get_queryset(self):
        return Student.objects.select_related(
            'institute',
            'contact_details',
            'education_details',
            'course_details',
            'admission_details',
            'course_assignments',
            'fee_details',
            'system_details',
        ).all()

    def get_permissions(self):
        """retrieve uses student's personal key; all other actions require admin key."""
        if self.action == 'retrieve':
            return [PersonalKeyPermission()]
        elif self.action == 'list':
            return [AttendancePermission()]
        return [InstituteKeyPermission()]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()          # calls has_object_permission internally
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CoursesViewSet(ModelViewSet):
    queryset = StudentCourseDetails.objects.values('course_name').distinct()
    serializer_class = CourseSerializer


class StudentIdLookUpViewSet(APIView):
    def post(self, request):
        serializer = StudentIdLookUpSerializer(data=request.data)
        if serializer.is_valid():
            student = serializer.validated_data['student']
            return Response({
                'student_id': student.id, 'status': status.HTTP_200_OK
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentVerifyView(APIView):
    """
    POST /admin_students/verify/?institute=<institute_id>

    Body (JSON):
        {
            "personal_id": "<15-digit student personal ID>",
            "email": "<student email>"       ← use one of these
            "mobile": "<student mobile>"     ← or this
        }

    Returns: { "student_id": <int> }
    No admin key required — student authenticates with their own personal_id.
    """

    def post(self, request):
        # 1. Resolve institute from query param
        institute_id = request.query_params.get('institute') or request.data.get('institute')
        if not institute_id:
            return Response(
                {'detail': 'institute query param is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            institute = Institute.objects.get(pk=institute_id)
        except Institute.DoesNotExist:
            return Response({'detail': 'Institute not found.'}, status=status.HTTP_404_NOT_FOUND)

        # 2. Extract and validate body fields
        personal_id = request.data.get('personal_id', '').strip()
        email       = request.data.get('email', '').strip()
        mobile      = request.data.get('mobile', '').strip()

        if not personal_id:
            return Response(
                {'detail': 'personal_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not email and not mobile:
            return Response(
                {'detail': 'Either email or mobile is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Look up the student
        try:
            filters = {
                'institute': institute,
                'system_details__student_personal_id': personal_id,
            }
            if email:
                filters['contact_details__email'] = email
            else:
                filters['contact_details__mobile'] = mobile

            student = Student.objects.get(**filters)
        except Student.DoesNotExist:
            return Response(
                {'detail': 'No student found with the provided credentials.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({'student_id': student.id}, status=status.HTTP_200_OK)



class SubjectsAssignedView(APIView):
    """
    GET    /admin_students/subjects/?institute=<id>              → all subjects
    GET    /admin_students/subjects/<student_id>/?institute=<id> → subjects for one student
    POST   /admin_students/subjects/?institute=<id>
    PUT    /admin_students/subjects/<pk>/?institute=<id>
    DELETE /admin_students/subjects/<pk>/?institute=<id>

    All actions require X-Admin-Key header (32-char admin key).
    """
    permission_classes = [InstituteKeyPermission]

    def get(self, request, pk=None):
        """List subjects. pk in the URL path is treated as student_id."""
        institute = request._verified_institute

        queryset = SubjectsAssigned.objects.filter(student__institute=institute)
        if pk is not None:
            # /subjects/<student_id>/ — filter by student
            queryset = queryset.filter(student_id=pk)
        elif request.query_params.get('student'):
            queryset = queryset.filter(student_id=request.query_params['student'])

        serializer = SubjectsAssignedSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk=None):
        """Assign one or more subjects to a student.

        POST /subjects/<student_id>/  → pk is the student id; body only needs subject+unit
        POST /subjects/               → body must include student field
        """
        many = isinstance(request.data, list)

        if pk is not None:
            # pk from URL is the student ID — inject it into each record
            if many:
                data = [{**item, 'student': pk} for item in request.data]
            else:
                data = {**request.data, 'student': pk}
        else:
            data = request.data

        serializer = SubjectsAssignedSerializer(data=data, many=many)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        """Update a specific subject assignment by its ID."""
        try:
            obj = SubjectsAssigned.objects.get(pk=pk, student__institute=request._verified_institute)
        except SubjectsAssigned.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SubjectsAssignedSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a specific subject assignment by its ID."""
        try:
            obj = SubjectsAssigned.objects.get(pk=pk, student__institute=request._verified_institute)
        except SubjectsAssigned.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        obj.delete()
        return Response({'detail': 'Subject assignment deleted.'}, status=status.HTTP_200_OK)

class StudentFetchByPersonalKeyView(APIView):
    """
    POST /admin_students/fetch-by-key/
    Accepts {"personal_id": "<16-digit-key>"}
    Returns the student's full data if the personal_id matches.
    Does NOT require an admin key — uses the student's own personal key.
    """

    def post(self, request):
        personal_id = request.data.get('personal_id')

        if not personal_id:
            return Response(
                {'detail': 'personal_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = Student.objects.select_related(
                'institute',
                'contact_details',
                'education_details',
                'course_details',
                'admission_details',
                'course_assignments',
                'fee_details',
                'system_details',
            ).get(system_details__student_personal_id=personal_id)
        except Student.DoesNotExist:
            return Response(
                {'detail': 'No student found with the given personal ID.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check that the institute is active
        if student.institute and not student.institute.is_event_active:
            return Response(
                {'detail': f'Institute events are currently {student.institute.event_status}. Access denied.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = StudentSerializer(student)
        return Response(serializer.data)

