from collections import OrderedDict

from activity_feed.services import log_activity

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    STUDENT_ACCESS_CONTROL,
    InstituteKeyPermission,
)
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
    'contact_details__parmannent_address',
    'contact_details__current_address',
    'contact_details__mobile',
    'contact_details__father_name',
    'contact_details__mother_name',
    'contact_details__guardian_name',
    'contact_details__parent_contact',
    'education_details__qualification',
    'education_details__passing_year',
    'education_details__instutute_name',
    'education_details__marks_obtained',
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
            'parmannent_address': contact.parmannent_address if contact else '',
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
            'instutute_name': education.instutute_name if education else '',
            'marks_obtained': education.marks_obtained if education else '',
        },
        'admission_details': {
            'enrollment_number': admission.enrollment_number if admission else '',
            'roll_number': admission.roll_number if admission else '',
            'admission_date': serialize_date(admission.admission_date) if admission else None,
            'academic_year': admission.academic_year if admission else '',
        },
        'course_assignment': {
            'class_name': course.class_name if course else '',
            'branch': course.branch if course else '',
            'academic_term': course.academic_term if course else '',
        },
        'fee_details': {
            'total_fee_amount': fee.total_fee_amount if fee else 0.0,
            'paid_amount': fee.paid_amount if fee else 0.0,
            'pending_amount': fee.pending_amount if fee else 0.0,
        },
        'system_details': {
            'student_personal_id': system.student_personal_id if system else '',
            'library_card_number': system.library_card_number if system else '',
            'hostel_details': system.hostel_details if system else '',
            'varification_status': system.varification_status if system else '',
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


def snapshot_has_changed(existing, student_name, student_personal_id, student_data, subjects_data):
    return any([
        existing.name != student_name,
        existing.student_personal_id != student_personal_id,
        existing.student_data != student_data,
        existing.subjects_assigned != subjects_data,
    ])


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
        serializer = PublishedStudentSerializer(
            get_published_student_queryset(institute),
            many=True,
        )
        return Response(build_institute_response(institute, serializer.data))

    def post(self, request):
        institute = request._verified_institute
        students = list(get_student_publish_queryset(institute))
        existing_map = {
            snapshot.source_student_id: snapshot
            for snapshot in PublishedStudent.objects.filter(institute=institute).only(
                'id',
                'source_student_id',
                'name',
                'student_personal_id',
                'student_data',
                'subjects_assigned',
                'published_at',
                'updated_at',
            )
        }

        now = timezone.now()
        current_student_ids = set()
        create_objects = []
        update_objects = []
        already_exists_count = 0
        already_exists_student_ids = []

        for student in students:
            current_student_ids.add(student.id)
            student_data = build_student_snapshot(student)
            subjects_data = build_subjects_snapshot(student)
            existing = existing_map.get(student.id)
            student_personal_id = student_data['system_details']['student_personal_id']

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
                continue

            if not snapshot_has_changed(
                existing,
                student.name,
                student_personal_id,
                student_data,
                subjects_data,
            ):
                already_exists_count += 1
                already_exists_student_ids.append(student.id)
                continue

            existing.name = student.name
            existing.student_personal_id = student_personal_id
            existing.student_data = student_data
            existing.subjects_assigned = subjects_data
            existing.updated_at = now
            update_objects.append(existing)

        if create_objects:
            PublishedStudent.objects.bulk_create(create_objects)
        if update_objects:
            PublishedStudent.objects.bulk_update(
                update_objects,
                ['name', 'student_personal_id', 'student_data', 'subjects_assigned', 'updated_at'],
            )

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
        }
        if already_exists_count:
            response_kwargs['message'] = 'The data already exist.'
            response_kwargs['already_exists_student_ids'] = already_exists_student_ids
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
