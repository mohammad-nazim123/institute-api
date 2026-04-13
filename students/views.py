from collections import OrderedDict

from activity_feed.services import ActivityLogMixin, log_activity

from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet
from .models import Student, StudentCourseAssignment, SubjectsAssigned
from rest_framework.views import APIView
from .serializers import StudentSerializer, StudentIdLookUpSerializer, SubjectsAssignedSerializer
from rest_framework.response import Response
from rest_framework import status
from institute_api.mixins import InstituteDictResponseMixin
from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    FEE_ACCESS_CONTROL,
    STUDENT_ACCESS_CONTROL,
    InstituteKeyPermission,
    StudentRetrievePermission,
    SubjectAssignmentPermission,
)
from iinstitutes_list.academic_terms import (
    canonicalize_institute_academic_term,
    filter_queryset_by_academic_term,
)
from iinstitutes_list.models import Institute
from institute_api.pagination import GracefulPageNumberPagination
from django.db.models import Q


class StudentPagination(GracefulPageNumberPagination):
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
    'education_details__institute_name',
    'education_details__marks_obtained',
    'contact_details__email',
    'contact_details__permanent_address',
    'contact_details__current_address',
    'contact_details__mobile',
    'contact_details__father_name',
    'contact_details__mother_name',
    'contact_details__guardian_name',
    'contact_details__parent_contact',
    'admission_details__enrollment_number',
    'admission_details__roll_number',
    'admission_details__admission_date',
    'admission_details__start_class_date',
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
    'system_details__verification_status',
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
            ('qualification', 'passing_year', 'institute_name', 'marks_obtained'),
        ),
        'contact_details': _build_related_payload(
            row,
            'contact_details',
            (
                'email',
                'permanent_address',
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
            (
                'enrollment_number',
                'roll_number',
                'admission_date',
                'start_class_date',
                'academic_year',
            ),
            date_fields=('admission_date', 'start_class_date'),
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
            ('student_personal_id', 'library_card_number', 'hostel_details', 'verification_status'),
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
    institute = getattr(request, '_verified_institute', None)
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

    return queryset


class StudentViewSet(ActivityLogMixin, InstituteDictResponseMixin, ModelViewSet):
    activity_entity_type = 'student'
    serializer_class = StudentSerializer
    entity_key = 'students'
    entity_name_field = 'name'
    pagination_class = StudentPagination
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
        FEE_ACCESS_CONTROL,
    )

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self._enforce_fee_access_scope(request)

    def _is_fee_access_request(self, request):
        return getattr(request, '_verified_access_control', '') == FEE_ACCESS_CONTROL

    def _is_fee_only_patch(self, request):
        if not isinstance(request.data, dict):
            return False

        payload_keys = set(request.data.keys())
        if not payload_keys or payload_keys - {'fee_details'}:
            return False

        fee_details = request.data.get('fee_details')
        if not isinstance(fee_details, dict) or not fee_details:
            return False

        return set(fee_details.keys()).issubset({
            'total_fee_amount',
            'paid_amount',
            'pending_amount',
        })

    def _enforce_fee_access_scope(self, request):
        if not self._is_fee_access_request(request):
            return

        if self.action in ('list',):
            return

        if self.action == 'partial_update' and self._is_fee_only_patch(request):
            return

        raise PermissionDenied('Fee access can only view students and update fee details.')

    def get_activity_entity_type(self, action, instance):
        if action == 'update' and self._is_fee_only_patch(self.request):
            return 'student fee'
        return super().get_activity_entity_type(action, instance)

    def get_queryset(self):
        request = getattr(self, 'request', None)
        institute = getattr(request, '_verified_institute', None) if request is not None else None
        queryset = get_student_detail_queryset(institute=institute)

        if request is None:
            return queryset

        return apply_student_filters(queryset, request)

    def get_permissions(self):
        """retrieve accepts admin or student key; all other actions require admin key."""
        if self.action == 'retrieve':
            return [StudentRetrievePermission()]
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
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )
    bulk_create_batch_size = 1000

    def _get_subject_payload(self, request):
        if isinstance(request.data, list):
            return request.data

        subjects = request.data.get('subjects') if hasattr(request.data, 'get') else None
        if subjects is not None:
            return subjects

        return request.data

    def _normalize_subject(self, subject):
        return ' '.join((subject or '').strip().lower().split())

    def _serialize_created_subjects(self, assignments):
        return [
            {
                'id': assignment.id,
                'student': assignment.student_id,
                'subject': assignment.subject,
                'unit': assignment.unit,
            }
            for assignment in assignments
        ]

    def _build_bulk_response_payload(
        self,
        created_assignments,
        duplicate_items,
        *,
        detail,
        extra_payload=None,
    ):
        payload = {
            'detail': detail,
            'created_subjects': self._serialize_created_subjects(created_assignments),
            'created_count': len(created_assignments),
            'already_assigned_count': len(duplicate_items),
        }
        if duplicate_items:
            payload['already_assigned'] = duplicate_items
            payload['message'] = (
                'Some subjects are already assigned.'
                if created_assignments
                else 'All provided subjects are already assigned.'
            )
        if extra_payload:
            payload.update(extra_payload)
        return payload

    def _log_bulk_subject_assignment(
        self,
        request,
        created_assignments,
        duplicate_items,
        *,
        extra_details=None,
    ):
        if not created_assignments:
            return

        subject_names = sorted({assignment.subject for assignment in created_assignments})
        student_ids = {assignment.student_id for assignment in created_assignments}
        if len(subject_names) == 1:
            entity_name = subject_names[0]
            description = f"{entity_name} was assigned to {len(student_ids)} students."
        else:
            entity_name = f"{len(created_assignments)} subject assignments"
            description = (
                f"{len(created_assignments)} subject assignments were created for "
                f"{len(student_ids)} students."
            )

        details = {
            'student_count': len(student_ids),
            'created_count': len(created_assignments),
            'already_assigned_count': len(duplicate_items),
            'subjects': subject_names,
        }
        if extra_details:
            details.update(extra_details)

        log_activity(
            request,
            action='create',
            entity_type='assigned subject',
            entity_name=entity_name,
            description=description,
            details=details,
        )

    def _find_duplicate_subjects(self, validated_items):
        student_ids = {
            item['student'].id if hasattr(item['student'], 'id') else item['student']
            for item in validated_items
        }
        existing_subjects = {}
        for student_id, subject in (
            SubjectsAssigned.objects
            .filter(student_id__in=student_ids)
            .values_list('student_id', 'subject')
        ):
            existing_subjects.setdefault(student_id, set()).add(self._normalize_subject(subject))

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

    def _validate_bulk_subject_payload(self, payload, institute):
        errors = []
        provisional_items = []
        student_ids = set()

        for item in payload:
            item_errors = {}

            if not isinstance(item, dict):
                errors.append({'non_field_errors': ['Each item must be an object.']})
                continue

            raw_student = item.get('student')
            if raw_student in (None, ''):
                item_errors['student'] = ['This field is required.']
                student_id = None
            else:
                try:
                    student_id = int(raw_student)
                except (TypeError, ValueError):
                    item_errors['student'] = ['A valid integer is required.']
                    student_id = None

            subject = str(item.get('subject') or '').strip()
            if not subject:
                item_errors['subject'] = ['This field is required.']

            unit = str(item.get('unit') or '').strip()
            if not unit:
                item_errors['unit'] = ['This field is required.']

            errors.append(item_errors)
            if item_errors:
                continue

            provisional_items.append({
                'index': len(errors) - 1,
                'student': student_id,
                'subject': subject,
                'unit': unit,
            })
            student_ids.add(student_id)

        valid_student_ids = set(
            Student.objects
            .filter(institute=institute, pk__in=student_ids)
            .values_list('id', flat=True)
        )

        validated_items = []
        for item in provisional_items:
            if item['student'] not in valid_student_ids:
                errors[item['index']]['student'] = [
                    f'Invalid pk "{item["student"]}" - object does not exist.'
                ]
                continue

            validated_items.append({
                'student': item['student'],
                'subject': item['subject'],
                'unit': item['unit'],
            })

        if any(item_errors for item_errors in errors):
            return None, errors

        return validated_items, None

    def _get_hierarchy_bulk_request(self, request):
        if not hasattr(request.data, 'get'):
            return None, None

        has_hierarchy_input = any(
            str(request.data.get(field) or '').strip()
            for field in ('class_name', 'branch', 'academic_term')
        )
        if not has_hierarchy_input:
            return None, None

        if request.data.get('student') not in (None, ''):
            return None, None

        institute = request._verified_institute
        payload = {
            'subject': str(request.data.get('subject') or '').strip(),
            'unit': str(request.data.get('unit') or '').strip(),
            'class_name': str(request.data.get('class_name') or '').strip(),
            'branch': str(request.data.get('branch') or '').strip(),
            'academic_term': canonicalize_institute_academic_term(
                institute,
                str(request.data.get('academic_term') or '').strip(),
            ),
        }

        errors = {}
        for field, value in payload.items():
            if not value:
                errors[field] = ['This field is required.']

        if errors:
            return None, errors

        return payload, None

    def _get_matching_student_ids(self, institute, hierarchy_payload):
        queryset = StudentCourseAssignment.objects.filter(student__institute=institute)
        queryset = queryset.filter(class_name__iexact=hierarchy_payload['class_name'])
        queryset = queryset.filter(branch__iexact=hierarchy_payload['branch'])
        queryset = filter_queryset_by_academic_term(
            queryset,
            'academic_term',
            hierarchy_payload['academic_term'],
            institute,
        )
        return list(
            queryset.order_by('student_id').values_list('student_id', flat=True)
        )

    def _create_bulk_subject_assignments(
        self,
        request,
        validated_items,
        *,
        created_detail,
        no_changes_detail,
        success_status=status.HTTP_201_CREATED,
        allow_no_changes_success=False,
        extra_response_payload=None,
        extra_log_details=None,
    ):
        creatable_items, duplicate_items = self._find_duplicate_subjects(validated_items)

        if not creatable_items:
            response_payload = self._build_bulk_response_payload(
                [],
                duplicate_items,
                detail=no_changes_detail,
                extra_payload=extra_response_payload,
            )
            response_status = (
                status.HTTP_200_OK
                if allow_no_changes_success
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(response_payload, status=response_status)

        created_assignments = SubjectsAssigned.objects.bulk_create(
            [
                SubjectsAssigned(
                    student_id=item['student'],
                    subject=item['subject'],
                    unit=item['unit'],
                )
                for item in creatable_items
            ],
            batch_size=self.bulk_create_batch_size,
        )
        self._log_bulk_subject_assignment(
            request,
            created_assignments,
            duplicate_items,
            extra_details=extra_log_details,
        )

        response_payload = self._build_bulk_response_payload(
            created_assignments,
            duplicate_items,
            detail=created_detail.format(created_count=len(created_assignments)),
            extra_payload=extra_response_payload,
        )
        return Response(response_payload, status=success_status)

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
        hierarchy_payload, hierarchy_errors = self._get_hierarchy_bulk_request(request)
        if hierarchy_errors is not None:
            return Response(hierarchy_errors, status=status.HTTP_400_BAD_REQUEST)

        if hierarchy_payload is not None:
            institute = request._verified_institute
            student_ids = self._get_matching_student_ids(institute, hierarchy_payload)
            if not student_ids:
                return Response(
                    {
                        'detail': 'No students found for the selected class, branch, and academic term.',
                        'created_subjects': [],
                        'created_count': 0,
                        'already_assigned_count': 0,
                        'matched_students': 0,
                        'class_name': hierarchy_payload['class_name'],
                        'branch': hierarchy_payload['branch'],
                        'academic_term': hierarchy_payload['academic_term'],
                    },
                    status=status.HTTP_200_OK,
                )

            validated_items = [
                {
                    'student': student_id,
                    'subject': hierarchy_payload['subject'],
                    'unit': hierarchy_payload['unit'],
                }
                for student_id in student_ids
            ]
            return self._create_bulk_subject_assignments(
                request,
                validated_items,
                created_detail='Assigned subject to {created_count} students.',
                no_changes_detail='Subject is already assigned to all matching students.',
                allow_no_changes_success=True,
                extra_response_payload={
                    'matched_students': len(student_ids),
                    'class_name': hierarchy_payload['class_name'],
                    'branch': hierarchy_payload['branch'],
                    'academic_term': hierarchy_payload['academic_term'],
                },
                extra_log_details={
                    'matched_students': len(student_ids),
                    'class_name': hierarchy_payload['class_name'],
                    'branch': hierarchy_payload['branch'],
                    'academic_term': hierarchy_payload['academic_term'],
                    'unit': hierarchy_payload['unit'],
                },
            )

        payload = self._get_subject_payload(request)
        many = isinstance(payload, list)

        if pk is not None:
            if many:
                data = [{**item, 'student': pk} for item in payload]
            else:
                data = {**payload, 'student': pk}
        else:
            data = payload

        if many:
            if not data:
                return Response(
                    {
                        'detail': 'At least one subject assignment is required.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            validated_items, validation_errors = self._validate_bulk_subject_payload(
                data,
                request._verified_institute,
            )
            if validation_errors is not None:
                return Response(validation_errors, status=status.HTTP_400_BAD_REQUEST)

            return self._create_bulk_subject_assignments(
                request,
                validated_items,
                created_detail='Created {created_count} subject assignments.',
                no_changes_detail='All provided subjects are already assigned.',
            )

        serializer = SubjectsAssignedSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_items = [serializer.validated_data]
        creatable_items, duplicate_items = self._find_duplicate_subjects(validated_items)

        if duplicate_items:
            return Response(
                {'detail': 'Subject already assigned for this student.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = serializer.save()
        log_activity(
            request,
            action='create',
            entity_type='assigned subject',
            entity_id=subject.id,
            entity_name=subject.subject,
            description=f"{subject.subject} was assigned to student #{subject.student_id}.",
            details={'student_id': subject.student_id, 'unit': subject.unit},
        )
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
            duplicate_exists = (
                SubjectsAssigned.objects
                .filter(student_id=obj.student_id, subject__iexact=new_subject)
                .exclude(pk=obj.pk)
                .exists()
            )
            if duplicate_exists:
                return Response(
                    {'detail': 'Subject already assigned for this student.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            subject = serializer.save()
            log_activity(
                request,
                action='update',
                entity_type='assigned subject',
                entity_id=subject.id,
                entity_name=subject.subject,
                description=f"{subject.subject} assignment was updated for student #{subject.student_id}.",
                details={'student_id': subject.student_id, 'unit': subject.unit},
            )
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

        deleted_payload = {
            'entity_id': obj.id,
            'entity_name': obj.subject,
            'description': f"{obj.subject} assignment was removed from student #{obj.student_id}.",
            'details': {'student_id': obj.student_id},
        }
        obj.delete()
        log_activity(
            request,
            action='delete',
            entity_type='assigned subject',
            entity_id=deleted_payload['entity_id'],
            entity_name=deleted_payload['entity_name'],
            description=deleted_payload['description'],
            details=deleted_payload['details'],
        )
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
