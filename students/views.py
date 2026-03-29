from collections import OrderedDict

from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import PageNumberPagination
from .models import Student, SubjectsAssigned
from rest_framework.views import APIView
from .serializers import StudentSerializer, StudentIdLookUpSerializer, SubjectsAssignedSerializer
from rest_framework.response import Response
from rest_framework import status
from institute_api.mixins import InstituteDictResponseMixin
from institute_api.permissions import InstituteKeyPermission, StudentPersonalKeyPermission, SubjectAssignmentPermission
from iinstitutes_list.models import Institute
from django.db.models import Q


class StudentPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200


STUDENT_LIST_VALUE_FIELDS = (
    'id',
    'institute_id',
    'name',
    'dob',
    'gender',
    'nationality',
    'identity',
    'category',
    'education_details__qualification',
    'education_details__passing_year',
    'education_details__instutute_name',
    'education_details__marks_obtained',
    'contact_details__email',
    'contact_details__parmannent_address',
    'contact_details__current_address',
    'contact_details__mobile',
    'contact_details__father_name',
    'contact_details__mother_name',
    'contact_details__guardian_name',
    'contact_details__parent_contact',
    'admission_details__enrollment_number',
    'admission_details__roll_number',
    'admission_details__admission_date',
    'admission_details__academic_year',
    'course_assignments__class_name',
    'course_assignments__branch',
    'course_assignments__academic_term',
    'fee_details__total_fee_amount',
    'fee_details__paid_amount',
    'fee_details__pending_amount',
    'system_details__student_personal_id',
    'system_details__library_card_number',
    'system_details__hostel_details',
    'system_details__varification_status',
)


def _serialize_date(value):
    return value.isoformat() if value else None


def _build_related_payload(row, prefix, fields, date_fields=()):
    values = {
        field: _serialize_date(row[f'{prefix}__{field}']) if field in date_fields else row[f'{prefix}__{field}']
        for field in fields
    }
    if all(value is None for value in values.values()):
        return None
    return values


def build_student_list_payload(row):
    return {
        'id': row['id'],
        'institute': row['institute_id'],
        'name': row['name'],
        'dob': _serialize_date(row['dob']),
        'gender': row['gender'],
        'nationality': row['nationality'],
        'identity': row['identity'],
        'category': row['category'],
        'education_details': _build_related_payload(
            row,
            'education_details',
            ('qualification', 'passing_year', 'instutute_name', 'marks_obtained'),
        ),
        'contact_details': _build_related_payload(
            row,
            'contact_details',
            (
                'email',
                'parmannent_address',
                'current_address',
                'mobile',
                'father_name',
                'mother_name',
                'guardian_name',
                'parent_contact',
            ),
        ),
        'admission_details': _build_related_payload(
            row,
            'admission_details',
            ('enrollment_number', 'roll_number', 'admission_date', 'academic_year'),
            date_fields=('admission_date',),
        ),
        'course_assignment': _build_related_payload(
            row,
            'course_assignments',
            ('class_name', 'branch', 'academic_term'),
        ),
        'fee_details': _build_related_payload(
            row,
            'fee_details',
            ('total_fee_amount', 'paid_amount', 'pending_amount'),
        ),
        'system_details': _build_related_payload(
            row,
            'system_details',
            ('student_personal_id', 'library_card_number', 'hostel_details', 'varification_status'),
        ),
    }


def get_student_detail_queryset(institute=None):
    queryset = Student.objects.select_related(
        'institute',
        'contact_details',
        'education_details',
        'admission_details',
        'course_assignments',
        'fee_details',
        'system_details',
    ).order_by('id')

    if institute is not None:
        queryset = queryset.filter(institute=institute)

    return queryset


def apply_student_filters(queryset, request):
    search = (request.query_params.get('search') or '').strip()
    if search:
        return queryset.filter(
            Q(name__icontains=search)
            | Q(contact_details__email__icontains=search)
            | Q(admission_details__enrollment_number__icontains=search)
            | Q(admission_details__roll_number__icontains=search)
            | Q(course_assignments__class_name__icontains=search)
            | Q(course_assignments__branch__icontains=search)
            | Q(course_assignments__academic_term__icontains=search)
            | Q(system_details__student_personal_id__icontains=search)
        )

    class_name = (request.query_params.get('class_name') or '').strip()
    branch = (request.query_params.get('branch') or '').strip()
    academic_term = (request.query_params.get('academic_term') or '').strip()

    if class_name:
        queryset = queryset.filter(course_assignments__class_name__iexact=class_name)
    if branch:
        queryset = queryset.filter(course_assignments__branch__iexact=branch)
    if academic_term:
        queryset = queryset.filter(course_assignments__academic_term__iexact=academic_term)

    return queryset


class StudentViewSet(InstituteDictResponseMixin, ModelViewSet):
    serializer_class = StudentSerializer
    entity_key = 'students'
    entity_name_field = 'name'
    pagination_class = StudentPagination

    def get_queryset(self):
        request = getattr(self, 'request', None)
        institute = getattr(request, '_verified_institute', None) if request is not None else None
        queryset = get_student_detail_queryset(institute=institute)

        if request is None:
            return queryset

        return apply_student_filters(queryset, request)

    def get_permissions(self):
        """retrieve uses student's personal key; all other actions require admin key."""
        if self.action == 'retrieve':
            return [StudentPersonalKeyPermission()]
        return [InstituteKeyPermission()]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()          # calls has_object_permission internally
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def _build_verified_institute_response(self, institute, serialized_data):
        return OrderedDict([
            ('id', institute.id),
            ('name', institute.name),
            ('students', serialized_data),
            ('professors', []),
            ('courses', []),
            ('weekly_schedules', []),
            ('exam_schedules', []),
            ('professors_payments', []),
        ])

    def list(self, request, *args, **kwargs):
        institute = request._verified_institute
        queryset = apply_student_filters(
            Student.objects.filter(institute=institute).order_by('id'),
            request,
        ).values(*STUDENT_LIST_VALUE_FIELDS)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serialized_data = [build_student_list_payload(row) for row in page]
            result = [self._build_verified_institute_response(institute, serialized_data)]
            return self.get_paginated_response(result)

        serialized_data = [build_student_list_payload(row) for row in queryset]
        return Response([self._build_verified_institute_response(institute, serialized_data)])


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
            "personal_id": "<student personal ID>",
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

            student = Student.objects.select_related(
                'contact_details', 'system_details'
            ).only(
                'id', 'institute_id',
                'contact_details__email', 'contact_details__mobile',
                'system_details__student_personal_id',
            ).get(**filters)
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

    Read:  X-Admin-Key (32-char) or X-Personal-Key (student personal ID)
    Write: X-Admin-Key only
    """
    permission_classes = [SubjectAssignmentPermission]

    def _get_subject_payload(self, request):
        if isinstance(request.data, list):
            return request.data

        subjects = request.data.get('subjects') if hasattr(request.data, 'get') else None
        if subjects is not None:
            return subjects

        return request.data

    def _normalize_subject(self, subject):
        return ' '.join((subject or '').strip().lower().split())

    def _find_duplicate_subjects(self, validated_items):
        student_ids = {
            item['student'].id if hasattr(item['student'], 'id') else item['student']
            for item in validated_items
        }
        existing_subjects = {}
        for row in (
            SubjectsAssigned.objects
            .filter(student_id__in=student_ids)
            .values('student_id', 'subject')
        ):
            existing_subjects.setdefault(row['student_id'], set()).add(
                self._normalize_subject(row['subject'])
            )

        request_subjects = {}
        creatable_items = []
        duplicate_items = []

        for item in validated_items:
            student = item['student']
            student_id = student.id if hasattr(student, 'id') else student
            subject = item['subject']
            normalized_subject = self._normalize_subject(subject)

            existing_for_student = existing_subjects.setdefault(student_id, set())
            requested_for_student = request_subjects.setdefault(student_id, set())

            if normalized_subject in existing_for_student or normalized_subject in requested_for_student:
                duplicate_items.append({
                    'student': student_id,
                    'subject': subject,
                    'message': 'Subject already assigned for this student.',
                })
                continue

            requested_for_student.add(normalized_subject)
            creatable_items.append(item)

        return creatable_items, duplicate_items

    def get(self, request, pk=None):
        """List subjects. pk in the URL path is treated as student_id."""
        institute = request._verified_institute

        queryset = (
            SubjectsAssigned.objects
            .select_related('student')
            .only('id', 'subject', 'unit', 'student_id', 'student__id', 'student__name')
            .filter(student__institute=institute)
        )
        verified_student = getattr(request, '_verified_student', None)
        if verified_student is not None:
            queryset = queryset.filter(student=verified_student)

        if pk is not None:
            queryset = queryset.filter(student_id=pk)
        elif request.query_params.get('student'):
            queryset = queryset.filter(student_id=request.query_params['student'])

        serializer = SubjectsAssignedSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk=None):
        """Assign one or more subjects to a student.

        POST /subjects/<student_id>/  → pk is the student id; body only needs subject+unit
        POST /subjects/               → body must include student field
        Uses bulk_create when a list is given — 1 INSERT for any number of subjects.
        """
        payload = self._get_subject_payload(request)
        many = isinstance(payload, list)

        if pk is not None:
            if many:
                data = [{**item, 'student': pk} for item in payload]
            else:
                data = {**payload, 'student': pk}
        else:
            data = payload

        serializer = SubjectsAssignedSerializer(data=data, many=many)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_items = serializer.validated_data if many else [serializer.validated_data]
        creatable_items, duplicate_items = self._find_duplicate_subjects(validated_items)

        if many:
            if not creatable_items:
                return Response(
                    {
                        'detail': 'All provided subjects are already assigned.',
                        'already_assigned': duplicate_items,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            objs = SubjectsAssigned.objects.bulk_create([
                SubjectsAssigned(**item) for item in creatable_items
            ])
            payload = {
                'created_subjects': SubjectsAssignedSerializer(objs, many=True).data,
            }
            if duplicate_items:
                payload['message'] = 'Some subjects are already assigned.'
                payload['already_assigned'] = duplicate_items
            return Response(payload, status=status.HTTP_201_CREATED)

        if duplicate_items:
            return Response(
                {'detail': 'Subject already assigned for this student.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        """Update a specific subject assignment by its ID."""
        try:
            obj = (
                SubjectsAssigned.objects
                .only('id', 'subject', 'unit', 'student_id')
                .get(pk=pk, student__institute=request._verified_institute)
            )
        except SubjectsAssigned.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SubjectsAssignedSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            new_subject = serializer.validated_data.get('subject', obj.subject)
            normalized_subject = self._normalize_subject(new_subject)
            duplicate_exists = (
                SubjectsAssigned.objects
                .filter(student_id=obj.student_id)
                .exclude(pk=obj.pk)
                .values_list('subject', flat=True)
            )
            if any(self._normalize_subject(subject) == normalized_subject for subject in duplicate_exists):
                return Response(
                    {'detail': 'Subject already assigned for this student.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a specific subject assignment by its ID."""
        try:
            obj = (
                SubjectsAssigned.objects
                .only('id', 'student_id')
                .get(pk=pk, student__institute=request._verified_institute)
            )
        except SubjectsAssigned.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        obj.delete()
        return Response({'detail': 'Subject assignment deleted.'}, status=status.HTTP_200_OK)

class StudentFetchByPersonalKeyView(APIView):
    """
    POST /admin_students/fetch-by-key/
    Accepts {"personal_id": "<student personal ID>"}
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
            student = get_student_detail_queryset().get(system_details__student_personal_id=personal_id)
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
