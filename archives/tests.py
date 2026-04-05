from datetime import date, time

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from attendance.models import Attendance
from employee_account_details.models import EmployeeAccountDetail
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
from set_exam_data.models import ExamData, ObtainedMarks
from students.models import (
    AttedanceDate,
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


class ArchiveApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            institute_name='Alpha Institute',
            super_admin_name='Primary Super Admin',
            admin_key='a' * 32,
        )
        self.other_institute = Institute.objects.create(
            institute_name='Beta Institute',
            super_admin_name='Backup Super Admin',
            admin_key='b' * 32,
        )
        self.super_admin_headers = {'HTTP_X_ADMIN_KEY': self.institute.admin_key}

        self.marking_professor = Professor.objects.create(
            institute=self.institute,
            name='Marker Professor',
            email='marker@example.com',
            phone_number='7777777777',
        )

        self.student = Student.objects.create(
            institute=self.institute,
            name='Alice',
            dob=date(2005, 1, 15),
            gender='Female',
            nationality='Indian',
            identity='AADHAR-1',
            category='General',
        )
        StudentContactDetails.objects.create(
            student=self.student,
            email='alice@example.com',
            parmannent_address='Permanent address',
            current_address='Current address',
            mobile='9999999999',
            father_name='Father',
            mother_name='Mother',
            guardian_name='Guardian',
            parent_contact='8888888888',
        )
        StudentEducationDetails.objects.create(
            student=self.student,
            qualification='12th',
            passing_year=2024,
            instutute_name='ABC School',
            marks_obtained='92',
        )
        StudentAdmissionDetails.objects.create(
            student=self.student,
            enrollment_number='ENR-1',
            roll_number='ROLL-1',
            admission_date=date(2025, 6, 1),
            academic_year='2025-26',
        )
        StudentCourseAssignment.objects.create(
            student=self.student,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
        )
        StudentFeeDetails.objects.create(
            student=self.student,
            total_fee_amount=100000,
            paid_amount=40000,
            pending_amount=60000,
        )
        StudentSystemDetails.objects.create(
            student=self.student,
            student_personal_id='STUDENT-0000001',
            library_card_number='LIB-1',
            hostel_details='Hostel A',
            varification_status='verified',
        )
        SubjectsAssigned.objects.bulk_create([
            SubjectsAssigned(student=self.student, subject='Math', unit='1'),
            SubjectsAssigned(student=self.student, subject='Physics', unit='2'),
        ])
        AttedanceDate.objects.create(
            student=self.student,
            date=date(2026, 3, 15),
        )
        self.student_attendance = Attendance.objects.create(
            student=self.student,
            date=date(2026, 3, 15),
            class_name='B.Tech',
            branch='CS',
            year_semester='Semester 1st',
            status=True,
            marked_by=self.marking_professor,
        )
        self.exam = ExamData.objects.create(
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            subject='Math',
            exam_type='Midterm',
            date=date(2026, 3, 20),
            duration=60,
            total_marks=100,
        )
        ObtainedMarks.objects.create(
            exam_data=self.exam,
            student=self.student,
            obtained_marks=86,
        )
        PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=self.student.id,
            name=self.student.name,
            student_personal_id='STUDENT-0000001',
            student_data={'id': self.student.id, 'name': self.student.name},
            subjects_assigned=[{'subject': 'Math', 'unit': '1'}],
        )

        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Bob',
            father_name='Father',
            mother_name='Mother',
            date_of_birth=date(1985, 2, 10),
            gender='Male',
            phone_number='8888888888',
            email='bob@example.com',
            indentity_number='AADHAR-PROF-1',
            marital_status='Single',
        )
        ProfessorAddress.objects.create(
            professor=self.professor,
            current_address='Current address',
            permanent_address='Permanent address',
            city='Kolkata',
            state='West Bengal',
            country='India',
        )
        ProfessorQualification.objects.bulk_create([
            ProfessorQualification(
                professor=self.professor,
                degree='M.Tech',
                institution='IIT',
                year_of_passing='2010',
                percentage='80',
                specialization='CSE',
            ),
            ProfessorQualification(
                professor=self.professor,
                degree='PhD',
                institution='NIT',
                year_of_passing='2015',
                percentage='85',
                specialization='AI',
            ),
        ])
        ProfessorExperience.objects.create(
            professor=self.professor,
            designation='Assistant Professor',
            department='CSE',
            teaching_subject='Python',
            teaching_experience='5',
            interest='Research',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='PROF00000000001',
            employee_id='EMP-1',
            date_of_joining=date(2021, 1, 10),
            employement_type='Full Time',
            working_hours='8',
            salary='50000',
        )
        professorClassAssigned.objects.create(
            professor=self.professor,
            assigned_course='B.Tech',
            assigned_section='A',
            assigned_year='3',
            session='2025-2026',
        )
        EmployeeAccountDetail.objects.create(
            institute=self.institute,
            professor=self.professor,
            account_holder_name='Dr Bob',
            bank_name='State Bank',
            account_number='12345678',
            ifsc_code='SBIN0123456',
        )
        ProfessorsPayments.objects.create(
            institute=self.institute,
            professor=self.professor,
            month_year='2026-03',
            payment_date=date(2026, 3, 31),
            payment_amount=50000,
            payment_status='paid',
        )
        PaymentNotification.objects.create(
            institute=self.institute,
            professor=self.professor,
            payment_month_key='2026-03',
            account_holder_name='Dr Bob',
            bank_name='State Bank',
            account_number='12345678',
            ifsc_code='SBIN0123456',
            final_amount='50000',
            payment_month='2026-03',
            payment_date='2026-03-31',
            approved_leaves='2',
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 29),
            status=True,
            attendance_time=time(9, 30),
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 28),
            comment='Medical leave',
            status=ProfessorLeave.STATUS_APPROVED,
        )
        self.professor_marked_attendance = Attendance.objects.create(
            student=self.student,
            date=date(2026, 3, 16),
            class_name='B.Tech',
            branch='CS',
            year_semester='Semester 1st',
            status=True,
            marked_by=self.professor,
        )
        PublishedProfessor.objects.create(
            institute=self.institute,
            source_professor_id=self.professor.id,
            name=self.professor.name,
            email=self.professor.email,
            professor_personal_id='PROF00000000001',
            professor_data={'id': self.professor.id, 'name': self.professor.name},
        )

    def archive_url(self, archive_id=None, institute_id=None):
        institute_id = institute_id or self.institute.id
        base = f'/institutes/archives/?institute={institute_id}'
        if archive_id is None:
            return base
        return f'/institutes/archives/{archive_id}/?institute={institute_id}'

    def test_create_archives_student_by_id_alias_and_deletes_live_records(self):
        response = self.client.post(
            self.archive_url(),
            data={
                'entity_type': ArchiveRecord.ENTITY_STUDENT,
                'id': self.student.id,
            },
            format='json',
            **self.super_admin_headers,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['name'], self.institute.name)
        self.assertEqual(response.data['archived_entity_type'], ArchiveRecord.ENTITY_STUDENT)
        self.assertEqual(response.data['archived_source_id'], self.student.id)
        self.assertEqual(len(response.data['archives']), 1)
        archived_student = response.data['archives'][0]
        self.assertEqual(archived_student['entity_type'], ArchiveRecord.ENTITY_STUDENT)
        self.assertEqual(archived_student['source_id'], self.student.id)
        self.assertEqual(archived_student['archived_data']['name'], 'Alice')
        self.assertEqual(
            archived_student['archived_data']['fee_details']['pending_amount'],
            60000,
        )
        self.assertEqual(len(archived_student['archived_data']['subjects_assigned']), 2)
        self.assertEqual(len(archived_student['archived_data']['attendance_dates']), 1)
        self.assertEqual(archived_student['archived_data']['obtained_marks'][0]['obtained_marks'], 86)

        self.assertFalse(Student.objects.filter(pk=self.student.id).exists())
        self.assertFalse(StudentContactDetails.objects.filter(student_id=self.student.id).exists())
        self.assertFalse(StudentFeeDetails.objects.filter(student_id=self.student.id).exists())
        self.assertFalse(Attendance.objects.filter(student_id=self.student.id).exists())
        self.assertFalse(ObtainedMarks.objects.filter(student_id=self.student.id).exists())
        self.assertFalse(
            PublishedStudent.objects.filter(
                institute=self.institute,
                source_student_id=self.student.id,
            ).exists()
        )

    def test_create_archives_professor_and_deletes_live_records(self):
        response = self.client.post(
            self.archive_url(),
            data={
                'entity_type': ArchiveRecord.ENTITY_PROFESSOR,
                'source_id': self.professor.id,
            },
            format='json',
            **self.super_admin_headers,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['archived_entity_type'], ArchiveRecord.ENTITY_PROFESSOR)
        self.assertEqual(response.data['archived_source_id'], self.professor.id)
        self.assertEqual(len(response.data['archives']), 1)
        archived_professor = response.data['archives'][0]
        self.assertEqual(archived_professor['name'], 'Dr Bob')
        self.assertEqual(
            archived_professor['archived_data']['admin_employement']['personal_id'],
            'PROF00000000001',
        )
        self.assertEqual(
            archived_professor['archived_data']['account_detail']['ifsc_code'],
            'SBIN0123456',
        )
        self.assertEqual(len(archived_professor['archived_data']['qualification']), 2)
        self.assertEqual(len(archived_professor['archived_data']['payments']), 1)
        self.assertEqual(len(archived_professor['archived_data']['marked_attendances']), 1)

        self.assertFalse(Professor.objects.filter(pk=self.professor.id).exists())
        self.assertFalse(ProfessorAddress.objects.filter(professor_id=self.professor.id).exists())
        self.assertFalse(professorAdminEmployement.objects.filter(professor_id=self.professor.id).exists())
        self.assertFalse(EmployeeAccountDetail.objects.filter(professor_id=self.professor.id).exists())
        self.assertFalse(ProfessorsPayments.objects.filter(professor_id=self.professor.id).exists())
        self.assertFalse(PaymentNotification.objects.filter(professor_id=self.professor.id).exists())
        self.assertFalse(
            PublishedProfessor.objects.filter(
                institute=self.institute,
                source_professor_id=self.professor.id,
            ).exists()
        )
        self.professor_marked_attendance.refresh_from_db()
        self.assertIsNone(self.professor_marked_attendance.marked_by_id)

    def test_archive_requires_matching_institute_super_admin_key(self):
        response = self.client.post(
            self.archive_url(),
            data={
                'entity_type': ArchiveRecord.ENTITY_STUDENT,
                'source_id': self.student.id,
            },
            format='json',
            HTTP_X_ADMIN_KEY=settings.ADMIN_KEY,
        )

        self.assertEqual(response.status_code, 403)

    def test_list_and_detail_are_scoped_to_institute(self):
        own_archive = ArchiveRecord.objects.create(
            institute=self.institute,
            entity_type=ArchiveRecord.ENTITY_STUDENT,
            source_id=999,
            name='Archived Alice',
            archived_data={'name': 'Alice'},
        )
        other_archive = ArchiveRecord.objects.create(
            institute=self.other_institute,
            entity_type=ArchiveRecord.ENTITY_PROFESSOR,
            source_id=888,
            name='Archived Other Professor',
            archived_data={'name': 'Other'},
        )

        list_response = self.client.get(
            self.archive_url(),
            **self.super_admin_headers,
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data['archives']), 1)
        self.assertEqual(list_response.data['archives'][0]['id'], own_archive.id)

        detail_response = self.client.get(
            self.archive_url(other_archive.id),
            **self.super_admin_headers,
        )
        self.assertEqual(detail_response.status_code, 404)

    def test_patch_updates_archive_fields(self):
        archive = ArchiveRecord.objects.create(
            institute=self.institute,
            entity_type=ArchiveRecord.ENTITY_STUDENT,
            source_id=777,
            name='Old Name',
            archived_data={'status': 'old'},
        )

        response = self.client.patch(
            self.archive_url(archive.id),
            data={
                'name': 'Archived Alice',
                'archived_data': {'status': 'updated'},
            },
            format='json',
            **self.super_admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['archives'][0]['name'], 'Archived Alice')
        self.assertEqual(response.data['archives'][0]['archived_data']['status'], 'updated')

        archive.refresh_from_db()
        self.assertEqual(archive.name, 'Archived Alice')
        self.assertEqual(archive.archived_data, {'status': 'updated'})

    def test_delete_removes_archive_record(self):
        archive = ArchiveRecord.objects.create(
            institute=self.institute,
            entity_type=ArchiveRecord.ENTITY_PROFESSOR,
            source_id=555,
            name='Archived Professor',
            archived_data={'name': 'Dr Bob'},
        )

        response = self.client.delete(
            self.archive_url(archive.id),
            **self.super_admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deleted_archive_id'], archive.id)
        self.assertFalse(ArchiveRecord.objects.filter(pk=archive.id).exists())
