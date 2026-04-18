from collections import OrderedDict

from activity_feed.services import log_activity

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from iinstitutes_list.academic_terms import (
    canonicalize_institute_academic_term,
    filter_queryset_by_academic_term,
)
from institute_api.pagination import StandardResultsPagination
from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    STUDENT_ACCESS_CONTROL,
    InstituteKeyPermission,
)
from published_schedules.models import PublishedExamSchedule, PublishedWeeklySchedule
from students.models import Student, SubjectsAssigned

from .models import PublishedStudent
from .permissions import PublishedStudentKeyPermission
from .serializers import PublishedStudentSerializer


STUDENT_ONLY_FIELDS = (
    'id',
    'institute_id',
    'name',
    'dob',
    'gender',
    'nationality',
    'identity',
    'category',
    'contact_details__email',
    'contact_details__permanent_address',
    'contact_details__current_address',
    'contact_details__mobile',
    'contact_details__father_name',
    'contact_details__mother_name',
    'contact_details__guardian_name',
    'contact_details__parent_contact',
    'education_details__qualification',
    'education_details__passing_year',
    'education_details__institute_name',
    'education_details__marks_obtained',
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

PUBLISHED_ONLY_FIELDS = (
    'id',
    'institute_id',
    'source_student_id',
    'name',
    'student_personal_id',
    'student_data',
    'subjects_assigned',
    'published_at',
    'updated_at',
)


def get_student_publish_queryset(institute):
    return (
        Student.objects
        .filter(institute=institute)
        .select_related(
            'contact_details',
            'education_details',
            'admission_details',
            'course_assignments',
            'fee_details',
            'system_details',
        )
        .prefetch_related(
            Prefetch(
                'subjects_assigned',
                queryset=SubjectsAssigned.objects.only(
                    'id',
                    'student_id',
                    'subject',
                    'unit',
                ).order_by('id'),
            )
        )
        .only(*STUDENT_ONLY_FIELDS)
        .order_by('id')
    )


def get_published_student_queryset(institute):
    return (
        PublishedStudent.objects
        .filter(institute=institute)
        .only(*PUBLISHED_ONLY_FIELDS)
        .order_by('source_student_id')
    )


def get_published_student_lookup_queryset(institute):
    return (
        PublishedStudent.objects
        .filter(institute=institute)
        .only('id', 'institute_id', 'source_student_id', 'student_personal_id')
        .order_by('source_student_id')
    )


def get_student_publish_scope(query_params, institute, payload=None):
    payload = payload or {}
    class_name = (query_params.get('class_name') or payload.get('class_name') or '').strip()
    branch = (query_params.get('branch') or payload.get('branch') or '').strip()
    academic_term = canonicalize_institute_academic_term(
        institute,
        (query_params.get('academic_term') or payload.get('academic_term') or '').strip(),
    )
    return {
        'class_name': class_name,
        'branch': branch,
        'academic_term': academic_term,
    }


def has_student_publish_scope(scope):
    return any([
        scope.get('class_name'),
        scope.get('branch'),
        scope.get('academic_term'),
    ])


def apply_student_publish_scope(
    queryset,
    institute,
    scope,
    class_field='course_assignments__class_name',
    branch_field='course_assignments__branch',
    academic_term_field='course_assignments__academic_term',
):
    class_name = scope.get('class_name') or ''
    branch = scope.get('branch') or ''
    academic_term = scope.get('academic_term') or ''

    if class_name:
        queryset = queryset.filter(**{f'{class_field}__iexact': class_name})
    if branch:
        queryset = queryset.filter(**{f'{branch_field}__iexact': branch})
    if academic_term:
        queryset = filter_queryset_by_academic_term(
            queryset,
            academic_term_field,
            academic_term,
            institute,
        )

    return queryset


def get_published_student_existing_map(institute, student_ids=None):
    queryset = PublishedStudent.objects.filter(institute=institute).only(
        'id',
        'source_student_id',
        'name',
        'student_personal_id',
        'student_data',
        'subjects_assigned',
        'published_at',
        'updated_at',
    )
    if student_ids is not None:
        queryset = queryset.filter(source_student_id__in=student_ids)

    return {
        snapshot.source_student_id: snapshot
        for snapshot in queryset
    }


def parse_student_ids(raw_ids):
    if raw_ids in (None, ''):
        return None

    if isinstance(raw_ids, (list, tuple)):
        values = raw_ids
    else:
        values = str(raw_ids).split(',')

    parsed_ids = []
    for value in values:
        normalized_value = str(value).strip()
        if not normalized_value:
            continue
        try:
            parsed_ids.append(int(normalized_value))
        except (TypeError, ValueError) as exc:
            raise ValueError('student_ids must be a comma-separated list of integers.') from exc

    return parsed_ids


def related_or_none(instance, attr):
    try:
        return getattr(instance, attr)
    except ObjectDoesNotExist:
        return None


def serialize_date(value):
    return value.isoformat() if value else None


def build_student_snapshot(student):
    contact = related_or_none(student, 'contact_details')
    education = related_or_none(student, 'education_details')
    admission = related_or_none(student, 'admission_details')
    course = related_or_none(student, 'course_assignments')
    fee = related_or_none(student, 'fee_details')
    system = related_or_none(student, 'system_details')

    return {
        'id': student.id,
        'name': student.name,
        'dob': serialize_date(student.dob),
        'gender': student.gender,
        'nationality': student.nationality,
        'identity': student.identity,
        'category': student.category,
        'contact_details': {
            'email': contact.email if contact else '',
            'permanent_address': contact.permanent_address if contact else '',
            'current_address': contact.current_address if contact else '',
            'mobile': contact.mobile if contact else '',
            'father_name': contact.father_name if contact else '',
            'mother_name': contact.mother_name if contact else '',
            'guardian_name': contact.guardian_name if contact else '',
            'parent_contact': contact.parent_contact if contact else '',
        },
        'education_details': {
            'qualification': education.qualification if education else '',
            'passing_year': education.passing_year if education else 0,
            'institute_name': education.institute_name if education else '',
            'marks_obtained': education.marks_obtained if education else '',
        },
        'admission_details': {
            'enrollment_number': admission.enrollment_number if admission else '',
            'roll_number': admission.roll_number if admission else '',
            'admission_date': serialize_date(admission.admission_date) if admission else None,
            'start_class_date': serialize_date(admission.start_class_date) if admission else None,
            'academic_year': admission.academic_year if admission else '',
        },
        'course_assignment': {
            'class_name': course.class_name if course else '',
            'branch': course.branch if course else '',
            'academic_term': course.academic_term if course else '',
        },
        'fee_details': {
            'total_fee_amount': float(fee.total_fee_amount) if fee else 0.0,
            'paid_amount': float(fee.paid_amount) if fee else 0.0,
            'pending_amount': float(fee.pending_amount) if fee else 0.0,
        },
        'system_details': {
            'student_personal_id': system.student_personal_id if system else '',
            'library_card_number': system.library_card_number if system else '',
            'hostel_details': system.hostel_details if system else '',
            'verification_status': system.verification_status if system else '',
        },
    }


def build_subjects_snapshot(student):
    return [
        {
            'id': subject.id,
            'subject': subject.subject,
            'unit': subject.unit,
        }
        for subject in student.subjects_assigned.all()
    ]


def get_publish_snapshot_parts(student):
    student_data = build_student_snapshot(student)
    subjects_data = build_subjects_snapshot(student)
    student_personal_id = student_data['system_details']['student_personal_id']
    return student_data, subjects_data, student_personal_id


def snapshot_has_changed(existing, student_name, student_personal_id, student_data, subjects_data):
    return any([
        existing.name != student_name,
        existing.student_personal_id != student_personal_id,
        existing.student_data != student_data,
        existing.subjects_assigned != subjects_data,
    ])


def get_student_publish_status(existing, student_name, student_personal_id, student_data, subjects_data):
    if existing is None:
        return 'new'

    if snapshot_has_changed(
        existing,
        student_name,
        student_personal_id,
        student_data,
        subjects_data,
    ):
        return 'update'

    return 'exist'


def build_institute_response(institute, published_students, **extra):
    payload = OrderedDict([
        ('id', institute.id),
        ('name', institute.name),
        ('published_students', published_students),
    ])
    for key, value in extra.items():
        payload[key] = value
    return payload


class PublishedStudentListView(APIView):
    permission_classes = [InstituteKeyPermission]
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def get(self, request):
        institute = request._verified_institute
        queryset = get_published_student_queryset(institute)

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = PublishedStudentSerializer(page, many=True)
            return paginator.get_paginated_response(build_institute_response(institute, serializer.data))

        serializer = PublishedStudentSerializer(queryset, many=True)
        return Response(build_institute_response(institute, serializer.data))

    def post(self, request):
        institute = request._verified_institute
        scope = get_student_publish_scope(request.query_params, institute, request.data)
        is_scoped_publish = has_student_publish_scope(scope)
        try:
            selected_student_ids = parse_student_ids(
                request.query_params.get('student_ids') or request.data.get('student_ids')
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        students_queryset = apply_student_publish_scope(
            get_student_publish_queryset(institute),
            institute,
            scope,
        )
        if selected_student_ids is not None:
            students_queryset = students_queryset.filter(id__in=selected_student_ids)

        is_targeted_publish = is_scoped_publish or selected_student_ids is not None
        students = list(
            students_queryset
        )
        student_ids = [student.id for student in students]
        existing_map = get_published_student_existing_map(
            institute,
            student_ids if is_targeted_publish else None,
        )

        now = timezone.now()
        current_student_ids = set()
        create_objects = []
        update_objects = []
        created_student_ids = []
        updated_student_ids = []
        already_exists_count = 0
        already_exists_student_ids = []

        for student in students:
            current_student_ids.add(student.id)
            student_data, subjects_data, student_personal_id = get_publish_snapshot_parts(student)
            existing = existing_map.get(student.id)

            if existing is None:
                create_objects.append(
                    PublishedStudent(
                        institute_id=institute.id,
                        source_student_id=student.id,
                        name=student.name,
                        student_personal_id=student_personal_id,
                        student_data=student_data,
                        subjects_assigned=subjects_data,
                        published_at=now,
                        updated_at=now,
                    )
                )
                created_student_ids.append(student.id)
                continue

            if get_student_publish_status(
                existing,
                student.name,
                student_personal_id,
                student_data,
                subjects_data,
            ) == 'exist':
                already_exists_count += 1
                already_exists_student_ids.append(student.id)
                continue

            existing.name = student.name
            existing.student_personal_id = student_personal_id
            existing.student_data = student_data
            existing.subjects_assigned = subjects_data
            existing.updated_at = now
            update_objects.append(existing)
            updated_student_ids.append(student.id)

        if create_objects:
            PublishedStudent.objects.bulk_create(create_objects)
        if update_objects:
            PublishedStudent.objects.bulk_update(
                update_objects,
                ['name', 'student_personal_id', 'student_data', 'subjects_assigned', 'updated_at'],
            )

        deleted_count = 0
        if not is_targeted_publish:
            stale_student_ids = set(existing_map).difference(current_student_ids)
            deleted_count = len(stale_student_ids)
            if deleted_count:
                PublishedStudent.objects.filter(
                    institute=institute,
                    source_student_id__in=stale_student_ids,
                ).delete()

        serializer = PublishedStudentSerializer(
            get_published_student_queryset(institute),
            many=True,
        )
        response_kwargs = {
            'created_count': len(create_objects),
            'updated_count': len(update_objects),
            'already_exists_count': already_exists_count,
            'deleted_count': deleted_count,
            'created_student_ids': created_student_ids,
            'updated_student_ids': updated_student_ids,
            'already_exists_student_ids': already_exists_student_ids,
        }
        if already_exists_count:
            response_kwargs['message'] = 'The data already exist.'
        if not create_objects and not update_objects and not deleted_count and already_exists_count:
            response_kwargs['detail'] = 'The data already exist.'

        log_activity(
            request,
            action='sync',
            entity_type='published student data',
            description=(
                f"Synced published student data. Created {len(create_objects)}, updated {len(update_objects)}, removed {deleted_count}."
            ),
            details=response_kwargs,
        )
        return Response(
            build_institute_response(
                institute,
                serializer.data,
                **response_kwargs,
            ),
            status=status.HTTP_200_OK,
        )


class PublishedStudentIdLookupView(APIView):
    permission_classes = [PublishedStudentKeyPermission]

    def get(self, request):
        institute = request._verified_institute
        personal_key = request._personal_key

        try:
            snapshot = get_published_student_lookup_queryset(institute).get(
                student_personal_id=personal_key,
            )
        except PublishedStudent.DoesNotExist:
            return Response(
                {'detail': 'Published student not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                'student_id': snapshot.source_student_id,
                'institute': institute.id,
            },
            status=status.HTTP_200_OK,
        )


class PublishedStudentDetailView(APIView):
    allowed_subordinate_access_controls = (
        ADMIN_ACCESS_CONTROL,
        STUDENT_ACCESS_CONTROL,
    )

    def get_permissions(self):
        if self.request.method == 'GET':
            return [PublishedStudentKeyPermission()]
        return [InstituteKeyPermission()]

    def _get_snapshot(self, institute, student_id):
        return get_published_student_queryset(institute).get(source_student_id=student_id)

    def get(self, request, student_id):
        institute = request._verified_institute
        try:
            snapshot = self._get_snapshot(institute, student_id)
        except PublishedStudent.DoesNotExist:
            return Response({'detail': 'Published student not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, snapshot)
        serializer = PublishedStudentSerializer(snapshot)
        return Response(build_institute_response(institute, [serializer.data]))

    def patch(self, request, student_id):
        return self._update(request, student_id, partial=True)

    def put(self, request, student_id):
        return self._update(request, student_id, partial=False)

    def _update(self, request, student_id, partial):
        institute = request._verified_institute
        try:
            snapshot = self._get_snapshot(institute, student_id)
        except PublishedStudent.DoesNotExist:
            return Response({'detail': 'Published student not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublishedStudentSerializer(snapshot, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        snapshot = serializer.save()
        log_activity(
            request,
            action='update',
            entity_type='published student data',
            entity_id=snapshot.id,
            entity_name=snapshot.name,
            description=f"Updated published student data for {snapshot.name}.",
            details={'student_id': student_id},
        )
        return Response(build_institute_response(institute, [PublishedStudentSerializer(snapshot).data]))

    def delete(self, request, student_id):
        institute = request._verified_institute
        try:
            snapshot = self._get_snapshot(institute, student_id)
        except PublishedStudent.DoesNotExist:
            return Response({'detail': 'Published student not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted_payload = {'entity_id': snapshot.id, 'entity_name': snapshot.name}
        snapshot.delete()
        log_activity(
            request,
            action='delete',
            entity_type='published student data',
            entity_id=deleted_payload['entity_id'],
            entity_name=deleted_payload['entity_name'],
            description=f"Deleted published student data for {deleted_payload['entity_name']}.",
            details={'student_id': student_id},
        )
        return Response(
            build_institute_response(institute, [], deleted_student_id=student_id),
            status=status.HTTP_200_OK,
        )


class PublishSingleStudentView(APIView):
    """
    POST /published_students/publish-student/?institute=<id>&student_id=<id>

    Creates or updates the published snapshot for a single student.
    Returns { "result": "created" | "updated" | "already_exists", "student_id": <id> }
    """
    permission_classes = [InstituteKeyPermission]
    allowed_subordinate_access_controls = (ADMIN_ACCESS_CONTROL,)

    def post(self, request):
        institute = request._verified_institute

        raw_id = request.query_params.get('student_id') or request.data.get('student_id')
        if not raw_id:
            return Response(
                {'detail': 'student_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            student_id = int(raw_id)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'student_id must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student = (
                Student.objects
                .filter(institute=institute, id=student_id)
                .select_related(
                    'contact_details',
                    'education_details',
                    'admission_details',
                    'course_assignments',
                    'fee_details',
                    'system_details',
                )
                .prefetch_related(
                    Prefetch(
                        'subjects_assigned',
                        queryset=SubjectsAssigned.objects.only(
                            'id', 'student_id', 'subject', 'unit',
                        ).order_by('id'),
                    )
                )
                .only(*STUDENT_ONLY_FIELDS)
                .get()
            )
        except Student.DoesNotExist:
            return Response(
                {'detail': 'Student not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        now = timezone.now()
        student_data, subjects_data, student_personal_id = get_publish_snapshot_parts(student)

        existing = (
            PublishedStudent.objects
            .filter(institute=institute, source_student_id=student_id)
            .only(
                'id', 'source_student_id', 'name', 'student_personal_id',
                'student_data', 'subjects_assigned', 'published_at', 'updated_at',
            )
            .first()
        )

        if existing is None:
            PublishedStudent.objects.create(
                institute_id=institute.id,
                source_student_id=student.id,
                name=student.name,
                student_personal_id=student_personal_id,
                student_data=student_data,
                subjects_assigned=subjects_data,
                published_at=now,
                updated_at=now,
            )
            result = 'created'
        elif not snapshot_has_changed(
            existing, student.name, student_personal_id, student_data, subjects_data
        ):
            result = 'already_exists'
        else:
            existing.name = student.name
            existing.student_personal_id = student_personal_id
            existing.student_data = student_data
            existing.subjects_assigned = subjects_data
            existing.updated_at = now
            existing.save(update_fields=[
                'name', 'student_personal_id', 'student_data',
                'subjects_assigned', 'updated_at',
            ])
            result = 'updated'

        return Response(
            {'result': result, 'student_id': student_id},
            status=status.HTTP_200_OK,
        )


def _extract_course_hierarchy(student_data):
    course = (student_data or {}).get('course_assignment') or {}
    return {
        'class_name': course.get('class_name') or '',
        'branch': course.get('branch') or '',
        'academic_term': course.get('academic_term') or '',
    }


def _fetch_published_schedule(model, institute, hierarchy):
    if not all(hierarchy.values()):
        return None

    queryset = model.objects.filter(
        institute=institute,
        class_name=hierarchy['class_name'],
        branch=hierarchy['branch'],
    )
    queryset = filter_queryset_by_academic_term(
        queryset,
        'academic_term',
        hierarchy['academic_term'],
        institute,
    )
    return queryset.first()


def _schedule_payload(entry):
    if entry is None:
        return {'schedule_data': [], 'published_id': None, 'updated_at': None}
    return {
        'schedule_data': entry.schedule_data or [],
        'published_id': entry.id,
        'updated_at': entry.updated_at.isoformat() if entry.updated_at else None,
    }


class PublishedStudentPortalBundleView(APIView):
    permission_classes = [PublishedStudentKeyPermission]

    def get(self, request):
        institute = request._verified_institute
        personal_key = request._personal_key

        try:
            snapshot = get_published_student_queryset(institute).get(
                student_personal_id=personal_key,
            )
        except PublishedStudent.DoesNotExist:
            return Response(
                {'detail': 'Published student not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        student_payload = PublishedStudentSerializer(snapshot).data
        hierarchy = _extract_course_hierarchy(snapshot.student_data)
        canonical_term = canonicalize_institute_academic_term(
            institute,
            hierarchy['academic_term'],
        )
        canonical_hierarchy = {
            'class_name': hierarchy['class_name'],
            'branch': hierarchy['branch'],
            'academic_term': canonical_term or hierarchy['academic_term'],
        }

        weekly_entry = _fetch_published_schedule(
            PublishedWeeklySchedule,
            institute,
            canonical_hierarchy,
        )
        exam_entry = _fetch_published_schedule(
            PublishedExamSchedule,
            institute,
            canonical_hierarchy,
        )

        payload = OrderedDict([
            ('institute', {'id': institute.id, 'name': institute.institute_name}),
            ('student', student_payload),
            ('hierarchy', canonical_hierarchy),
            ('weekly_schedule', _schedule_payload(weekly_entry)),
            ('exam_schedule', _schedule_payload(exam_entry)),
            ('generated_at', timezone.now().isoformat()),
        ])
        return Response(payload)
