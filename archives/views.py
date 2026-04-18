from collections import OrderedDict

from activity_feed.services import log_activity

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Prefetch
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.models import Attendance
from employee_account_details.models import EmployeeAccountDetail
from institute_api.pagination import StandardResultsPagination
from institute_api.permissions import InstituteKeyPermission
from iinstitutes_list.models import Institute
from payment_notification.models import PaymentNotification
from payments.models import ProfessorsPayments
from professor_attendance.models import ProfessorAttendance, ProfessorLeave
from published_professors.models import PublishedProfessor
from published_student.models import PublishedStudent
from professors.models import (
    Professor,
    ProfessorAddress,
    ProfessorExperience,
    ProfessorQualification,
    professorAdminEmployement,
    professorClassAssigned,
)
from set_exam_data.models import ObtainedMarks
from students.models import (
    AttendanceDate,
    Student,
    StudentAdmissionDetails,
    StudentContactDetails,
    StudentCourseAssignment,
    StudentEducationDetails,
    StudentFeeDetails,
    StudentSystemDetails,
    SubjectsAssigned,
)

from .models import ArchiveRecord
from .serializers import ArchiveCreateSerializer, ArchiveRecordSerializer


def serialize_date(value):
    return value.isoformat() if value else None


def serialize_time(value):
    return value.isoformat() if value else None


def serialize_datetime(value):
    return value.isoformat() if value else None


def related_or_none(instance, attr_name):
    try:
        return getattr(instance, attr_name)
    except ObjectDoesNotExist:
        return None


def get_requested_institute(request):
    institute_id = request.query_params.get('institute')
    if not institute_id and hasattr(request, 'data'):
        institute_id = request.data.get('institute')

    if not institute_id:
        raise serializers.ValidationError({'institute': ['This field is required.']})

    try:
        return Institute.objects.only('id', 'institute_name').get(pk=institute_id)
    except Institute.DoesNotExist as exc:
        raise serializers.ValidationError({'institute': ['Institute not found.']}) from exc


def build_institute_response(institute, archives, **extra):
    payload = OrderedDict([
        ('id', institute.id),
        ('name', institute.name),
        ('archives', archives),
    ])
    for key, value in extra.items():
        payload[key] = value
    return payload


def get_student_archive_queryset(institute, source_id=None):
    queryset = (
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
            Prefetch('subjects_assigned', queryset=SubjectsAssigned.objects.order_by('id')),
            Prefetch('attendance_dates', queryset=AttendanceDate.objects.order_by('id')),
            Prefetch(
                'attendances',
                queryset=Attendance.objects.select_related('marked_by').order_by('id'),
            ),
            Prefetch(
                'obtained_marks',
                queryset=ObtainedMarks.objects.select_related('exam_data').order_by('id'),
            ),
        )
        .order_by('id')
    )
    if source_id is not None:
        queryset = queryset.filter(pk=source_id)
    return queryset


def get_professor_archive_queryset(institute, source_id=None):
    queryset = (
        Professor.objects
        .filter(institute=institute)
        .select_related(
            'address',
            'experience',
            'admin_employement',
            'class_assigned',
            'account_detail',
        )
        .prefetch_related(
            Prefetch('qualification', queryset=ProfessorQualification.objects.order_by('id')),
            Prefetch('payments', queryset=ProfessorsPayments.objects.order_by('id')),
            Prefetch('payment_notifications', queryset=PaymentNotification.objects.order_by('id')),
            Prefetch(
                'professor_attendance_records',
                queryset=ProfessorAttendance.objects.order_by('id'),
            ),
            Prefetch(
                'professor_leave_records',
                queryset=ProfessorLeave.objects.order_by('id'),
            ),
            Prefetch(
                'attendance_set',
                queryset=Attendance.objects.select_related('student').order_by('id'),
            ),
        )
        .order_by('id')
    )
    if source_id is not None:
        queryset = queryset.filter(pk=source_id)
    return queryset


def build_student_snapshot(student):
    contact = related_or_none(student, 'contact_details')
    education = related_or_none(student, 'education_details')
    admission = related_or_none(student, 'admission_details')
    course = related_or_none(student, 'course_assignments')
    fee = related_or_none(student, 'fee_details')
    system = related_or_none(student, 'system_details')

    return {
        'id': student.id,
        'institute': student.institute_id,
        'name': student.name,
        'dob': serialize_date(student.dob),
        'gender': student.gender,
        'nationality': student.nationality,
        'identity': student.identity,
        'category': student.category,
        'contact_details': {
            'id': contact.id if contact else None,
            'email': contact.email if contact else '',
            'permanent_address': contact.permanent_address if contact else '',
            'current_address': contact.current_address if contact else '',
            'mobile': contact.mobile if contact else '',
            'father_name': contact.father_name if contact else '',
            'mother_name': contact.mother_name if contact else '',
            'guardian_name': contact.guardian_name if contact else '',
            'parent_contact': contact.parent_contact if contact else '',
        } if contact else None,
        'education_details': {
            'id': education.id if education else None,
            'qualification': education.qualification if education else '',
            'passing_year': education.passing_year if education else 0,
            'institute_name': education.institute_name if education else '',
            'marks_obtained': education.marks_obtained if education else '',
        } if education else None,
        'admission_details': {
            'id': admission.id if admission else None,
            'enrollment_number': admission.enrollment_number if admission else '',
            'roll_number': admission.roll_number if admission else '',
            'admission_date': serialize_date(admission.admission_date) if admission else None,
            'start_class_date': serialize_date(admission.start_class_date) if admission else None,
            'academic_year': admission.academic_year if admission else '',
        } if admission else None,
        'course_assignment': {
            'id': course.id if course else None,
            'class_name': course.class_name if course else '',
            'branch': course.branch if course else '',
            'academic_term': course.academic_term if course else '',
        } if course else None,
        'fee_details': {
            'id': fee.id if fee else None,
            'total_fee_amount': fee.total_fee_amount if fee else 0.0,
            'paid_amount': fee.paid_amount if fee else 0.0,
            'pending_amount': fee.pending_amount if fee else 0.0,
        } if fee else None,
        'system_details': {
            'id': system.id if system else None,
            'student_personal_id': system.student_personal_id if system else '',
            'library_card_number': system.library_card_number if system else '',
            'hostel_details': system.hostel_details if system else '',
            'verification_status': system.verification_status if system else '',
        } if system else None,
        'subjects_assigned': [
            {
                'id': subject.id,
                'subject': subject.subject,
                'unit': subject.unit,
            }
            for subject in student.subjects_assigned.all()
        ],
        'attendance_dates': [
            {
                'id': attendance_date.id,
                'date': serialize_date(attendance_date.date),
            }
            for attendance_date in student.attendance_dates.all()
        ],
        'attendances': [
            {
                'id': attendance.id,
                'date': serialize_date(attendance.date),
                'class_name': attendance.class_name,
                'branch': attendance.branch,
                'year_semester': attendance.year_semester,
                'status': attendance.status,
                'marked_by': attendance.marked_by_id,
                'marked_by_name': attendance.marked_by.name if attendance.marked_by else '',
            }
            for attendance in student.attendances.all()
        ],
        'obtained_marks': [
            {
                'id': mark.id,
                'obtained_marks': mark.obtained_marks,
                'exam_data': {
                    'id': mark.exam_data_id,
                    'class_name': mark.exam_data.class_name,
                    'branch': mark.exam_data.branch,
                    'academic_term': mark.exam_data.academic_term,
                    'subject': mark.exam_data.subject,
                    'exam_type': mark.exam_data.exam_type,
                    'date': serialize_date(mark.exam_data.date),
                    'duration': mark.exam_data.duration,
                    'total_marks': mark.exam_data.total_marks,
                } if mark.exam_data_id else None,
            }
            for mark in student.obtained_marks.all()
        ],
    }


def build_professor_snapshot(professor):
    address = related_or_none(professor, 'address')
    experience = related_or_none(professor, 'experience')
    admin_employement = related_or_none(professor, 'admin_employement')
    class_assigned = related_or_none(professor, 'class_assigned')
    account_detail = related_or_none(professor, 'account_detail')

    return {
        'id': professor.id,
        'institute': professor.institute_id,
        'name': professor.name,
        'father_name': professor.father_name,
        'mother_name': professor.mother_name,
        'date_of_birth': serialize_date(professor.date_of_birth),
        'gender': professor.gender,
        'phone_number': professor.phone_number,
        'email': professor.email,
        'indentity_number': professor.indentity_number,
        'marital_status': professor.marital_status,
        'address': {
            'id': address.id if address else None,
            'current_address': address.current_address if address else '',
            'permanent_address': address.permanent_address if address else '',
            'city': address.city if address else '',
            'state': address.state if address else '',
            'country': address.country if address else '',
        } if address else None,
        'qualification': [
            {
                'id': qualification.id,
                'degree': qualification.degree,
                'institution': qualification.institution,
                'year_of_passing': qualification.year_of_passing,
                'percentage': qualification.percentage,
                'specialization': qualification.specialization,
            }
            for qualification in professor.qualification.all()
        ],
        'experience': {
            'id': experience.id if experience else None,
            'designation': experience.designation if experience else '',
            'department': experience.department if experience else '',
            'teaching_subject': experience.teaching_subject if experience else '',
            'teaching_experience': experience.teaching_experience if experience else '',
            'interest': experience.interest if experience else '',
        } if experience else None,
        'admin_employement': {
            'id': admin_employement.id if admin_employement else None,
            'personal_id': admin_employement.personal_id if admin_employement else '',
            'employee_id': admin_employement.employee_id if admin_employement else '',
            'date_of_joining': serialize_date(admin_employement.date_of_joining) if admin_employement else None,
            'employement_type': admin_employement.employement_type if admin_employement else '',
            'working_hours': admin_employement.working_hours if admin_employement else '',
            'salary': admin_employement.salary if admin_employement else '',
        } if admin_employement else None,
        'class_assigned': {
            'id': class_assigned.id if class_assigned else None,
            'assigned_course': class_assigned.assigned_course if class_assigned else '',
            'assigned_section': class_assigned.assigned_section if class_assigned else '',
            'assigned_year': class_assigned.assigned_year if class_assigned else '',
            'session': class_assigned.session if class_assigned else '',
        } if class_assigned else None,
        'account_detail': {
            'id': account_detail.id if account_detail else None,
            'account_holder_name': account_detail.account_holder_name if account_detail else '',
            'bank_name': account_detail.bank_name if account_detail else '',
            'account_number': account_detail.account_number if account_detail else '',
            'ifsc_code': account_detail.ifsc_code if account_detail else '',
            'created_at': serialize_datetime(account_detail.created_at) if account_detail else None,
            'updated_at': serialize_datetime(account_detail.updated_at) if account_detail else None,
        } if account_detail else None,
        'payments': [
            {
                'id': payment.id,
                'month_year': payment.month_year,
                'payment_date': serialize_date(payment.payment_date),
                'payment_amount': payment.payment_amount,
                'payment_status': payment.payment_status,
            }
            for payment in professor.payments.all()
        ],
        'payment_notifications': [
            {
                'id': notification.id,
                'payment_month_key': notification.payment_month_key,
                'account_holder_name': notification.account_holder_name,
                'bank_name': notification.bank_name,
                'account_number': notification.account_number,
                'ifsc_code': notification.ifsc_code,
                'gross_amount': notification.gross_amount,
                'deducted_amount': notification.deducted_amount,
                'final_amount': notification.final_amount,
                'payment_month': notification.payment_month,
                'payment_date': notification.payment_date,
                'approved_leaves': notification.approved_leaves,
                'status': notification.status,
                'created_at': serialize_datetime(notification.created_at),
                'updated_at': serialize_datetime(notification.updated_at),
            }
            for notification in professor.payment_notifications.all()
        ],
        'professor_attendance_records': [
            {
                'id': attendance.id,
                'date': serialize_date(attendance.date),
                'status': attendance.status,
                'attendance_time': serialize_time(attendance.attendance_time),
            }
            for attendance in professor.professor_attendance_records.all()
        ],
        'professor_leave_records': [
            {
                'id': leave.id,
                'date': serialize_date(leave.date),
                'comment': leave.comment,
                'status': leave.status,
            }
            for leave in professor.professor_leave_records.all()
        ],
        'marked_attendances': [
            {
                'id': attendance.id,
                'student': attendance.student_id,
                'student_name': attendance.student.name if attendance.student_id else '',
                'date': serialize_date(attendance.date),
                'class_name': attendance.class_name,
                'branch': attendance.branch,
                'year_semester': attendance.year_semester,
                'status': attendance.status,
            }
            for attendance in professor.attendance_set.all()
        ],
    }


class ArchiveListCreateView(APIView):
    permission_classes = [InstituteKeyPermission]

    def get(self, request):
        institute = get_requested_institute(request)
        queryset = ArchiveRecord.objects.filter(institute=institute).order_by('-archived_at', '-id')

        entity_type = (request.query_params.get('entity_type') or '').strip().lower()
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = ArchiveRecordSerializer(page, many=True)
            return paginator.get_paginated_response(build_institute_response(institute, serializer.data))

        serializer = ArchiveRecordSerializer(queryset, many=True)
        return Response(build_institute_response(institute, serializer.data))

    def post(self, request):
        institute = get_requested_institute(request)
        input_serializer = ArchiveCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        entity_type = input_serializer.validated_data['entity_type']
        source_id = input_serializer.validated_data['source_id']

        if ArchiveRecord.objects.filter(
            institute=institute,
            entity_type=entity_type,
            source_id=source_id,
        ).exists():
            return Response(
                {'detail': 'This record is already archived.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if entity_type == ArchiveRecord.ENTITY_STUDENT:
            try:
                source_instance = get_student_archive_queryset(institute, source_id=source_id).get()
            except Student.DoesNotExist:
                return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
            archive_name = source_instance.name
            archived_data = build_student_snapshot(source_instance)
        else:
            try:
                source_instance = get_professor_archive_queryset(institute, source_id=source_id).get()
            except Professor.DoesNotExist:
                return Response({'detail': 'Professor not found.'}, status=status.HTTP_404_NOT_FOUND)
            archive_name = source_instance.name
            archived_data = build_professor_snapshot(source_instance)

        with transaction.atomic():
            archive = ArchiveRecord.objects.create(
                institute=institute,
                entity_type=entity_type,
                source_id=source_id,
                name=archive_name,
                archived_data=archived_data,
            )
            if entity_type == ArchiveRecord.ENTITY_STUDENT:
                PublishedStudent.objects.filter(
                    institute=institute,
                    source_student_id=source_id,
                ).delete()
            else:
                PublishedProfessor.objects.filter(
                    institute=institute,
                    source_professor_id=source_id,
                ).delete()
            source_instance.delete()

        serializer = ArchiveRecordSerializer(archive)
        log_activity(
            request,
            institute=institute,
            action='archive',
            entity_type='archive record',
            entity_id=archive.id,
            entity_name=archive_name,
            description=f"Archived {archive_name} from {entity_type} records.",
            details={'entity_type': entity_type, 'source_id': source_id},
        )
        return Response(
            build_institute_response(
                institute,
                [serializer.data],
                archived_entity_type=entity_type,
                archived_source_id=source_id,
            ),
            status=status.HTTP_201_CREATED,
        )


class ArchiveDetailView(APIView):
    permission_classes = [InstituteKeyPermission]

    def _get_archive(self, request, pk):
        institute = get_requested_institute(request)
        try:
            archive = ArchiveRecord.objects.get(pk=pk, institute=institute)
        except ArchiveRecord.DoesNotExist:
            return institute, None
        return institute, archive

    def get(self, request, pk):
        institute, archive = self._get_archive(request, pk)
        if archive is None:
            return Response({'detail': 'Archive not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ArchiveRecordSerializer(archive)
        return Response(build_institute_response(institute, [serializer.data]))

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def _update(self, request, pk, partial):
        institute, archive = self._get_archive(request, pk)
        if archive is None:
            return Response({'detail': 'Archive not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ArchiveRecordSerializer(archive, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        archive = serializer.save()
        log_activity(
            request,
            institute=institute,
            action='update',
            entity_type='archive record',
            entity_id=archive.id,
            entity_name=archive.name,
            description=f"Updated archive record for {archive.name}.",
            details={'entity_type': archive.entity_type, 'source_id': archive.source_id},
        )
        return Response(build_institute_response(institute, [ArchiveRecordSerializer(archive).data]))

    def delete(self, request, pk):
        institute, archive = self._get_archive(request, pk)
        if archive is None:
            return Response({'detail': 'Archive not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted_payload = {'archive_id': archive.id, 'name': archive.name, 'entity_type': archive.entity_type, 'source_id': archive.source_id}
        archive.delete()
        log_activity(
            request,
            institute=institute,
            action='delete',
            entity_type='archive record',
            entity_id=deleted_payload['archive_id'],
            entity_name=deleted_payload['name'],
            description=f"Deleted archive record for {deleted_payload['name']}.",
            details={'entity_type': deleted_payload['entity_type'], 'source_id': deleted_payload['source_id']},
        )
        archive_id = deleted_payload['archive_id']
        return Response(
            build_institute_response(institute, [], deleted_archive_id=archive_id),
            status=status.HTTP_200_OK,
        )
