from datetime import date, time

from attendance.models import Attendance
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from published_exam_result.models import PublishedExamResult
from published_schedules.models import PublishedExamSchedule, PublishedWeeklySchedule
from published_student.models import PublishedStudent
from rest_framework.test import APIClient
from set_exam_data.models import ExamData
from weekly_exam_schedule.models import (
    ExamScheduleData,
    ExamScheduleDate,
    WeeklyScheduleData,
    WeeklyScheduleDay,
)

from professors.models import (
    Professor,
    ProfessorAddress,
    ProfessorExperience,
    ProfessorQualification,
    professorAdminEmployement,
    professorClassAssigned,
)
from students.models import (
    Student,
    StudentAdmissionDetails,
    StudentContactDetails,
    StudentCourseAssignment,
    StudentEducationDetails,
    StudentFeeDetails,
    StudentSystemDetails,
)
from syllabus.models import AcademicTerms, Branch, Course, Subject

from .academic_terms import sync_institute_academic_terms
from .admin import InstituteAdminForm
from .models import Institute


class InstituteDetailApiTests(TestCase):
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

        student = Student.objects.create(
            institute=self.institute,
            name='Alice',
            category='General',
        )
        StudentContactDetails.objects.create(
            student=student,
            email='alice@example.com',
            mobile='9999999999',
        )
        StudentEducationDetails.objects.create(
            student=student,
            qualification='Higher Secondary',
            passing_year=2024,
        )
        StudentAdmissionDetails.objects.create(
            student=student,
            enrollment_number='ENR-1',
            roll_number='ROLL-1',
            admission_date=date(2025, 6, 1),
            academic_year='2025-26',
        )
        StudentCourseAssignment.objects.create(
            student=student,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
        )
        StudentFeeDetails.objects.create(
            student=student,
            total_fee_amount=1000,
            paid_amount=500,
            pending_amount=500,
        )
        StudentSystemDetails.objects.create(
            student=student,
            student_personal_id='STU-1',
            library_card_number='LIB-1',
        )

        professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Bob',
            email='bob@example.com',
            phone_number='8888888888',
        )
        ProfessorAddress.objects.create(
            professor=professor,
            city='Kolkata',
        )
        ProfessorQualification.objects.create(
            professor=professor,
            degree='M.Tech',
            institution='IIT',
            specialization='AI',
        )
        ProfessorExperience.objects.create(
            professor=professor,
            department='CSE',
        )
        professorAdminEmployement.objects.create(
            professor=professor,
            personal_id='PROF-1',
            employee_id='EMP-1',
        )
        professorClassAssigned.objects.create(
            professor=professor,
            assigned_course='B.Tech',
            assigned_section='A',
        )

        course = Course.objects.create(
            institute=self.institute,
            name='B.Tech',
        )
        branch = Branch.objects.create(
            course=course,
            name='Computer Science',
        )
        term = AcademicTerms.objects.create(
            branch=branch,
            name='Semester 1st',
        )
        Subject.objects.create(
            academic_terms=term,
            name='Mathematics',
            unit=1,
        )

    def test_retrieve_returns_nested_dictionary_format(self):
        response = self.client.get(f'/institutes/institute/{self.institute.id}/')

        self.assertEqual(response.status_code, 200)
        payload = response.data[0]
        self.assertEqual(payload['name'], 'Alpha Institute')
        self.assertEqual(payload['institute_name'], 'Alpha Institute')
        self.assertEqual(payload['super_admin_name'], 'Primary Super Admin')
        self.assertIn('Alice', payload['students'])
        self.assertIn('Dr Bob', payload['professors'])
        self.assertIn('B.Tech', payload['courses'])
        self.assertEqual(
            payload['courses']['B.Tech']['branches'][0]['academic_terms'][0]['subjects'][0]['name'],
            'Mathematics',
        )
        self.assertEqual(payload['academic_terms_type'], 'semester')
        self.assertEqual(payload['academic_terms'][0], '1st Semester')

    def test_retrieve_uses_eight_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f'/institutes/institute/{self.institute.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 8)

    def test_list_uses_eight_queries_or_less_across_multiple_institutes(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/institutes/institute/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertLessEqual(len(queries), 8)

    def test_verify_uses_eight_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                '/institutes/verify/',
                data={
                    'institute_name': self.institute.institute_name,
                    'super_admin_name': self.institute.super_admin_name,
                    'admin_key': self.institute.admin_key,
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Alpha Institute')
        self.assertEqual(response.data['institute_name'], 'Alpha Institute')
        self.assertEqual(response.data['super_admin_name'], 'Primary Super Admin')
        self.assertEqual(response.data['academic_terms_type'], 'semester')
        self.assertEqual(response.data['academic_terms'][0], '1st Semester')
        self.assertLessEqual(len(queries), 8)

    def test_verify_rejects_when_super_admin_name_does_not_match(self):
        response = self.client.post(
            '/institutes/verify/',
            data={
                'institute_name': self.institute.institute_name,
                'super_admin_name': 'Wrong Super Admin',
                'admin_key': self.institute.admin_key,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['detail'], 'Super admin name does not match.')

    def test_verify_requires_super_admin_name_for_32_char_admin_key(self):
        response = self.client.post(
            '/institutes/verify/',
            data={
                'institute_name': self.institute.institute_name,
                'admin_key': self.institute.admin_key,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['super_admin_name'][0], 'Super admin name is required.')

    def test_create_accepts_institute_name_and_super_admin_name(self):
        response = self.client.post(
            '/institutes/institute/',
            data={
                'institute_name': 'Gamma Institute',
                'super_admin_name': 'Gamma Super Admin',
                'academic_terms_type': 'year',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['institute_name'], 'Gamma Institute')
        self.assertEqual(response.data['name'], 'Gamma Institute')
        self.assertEqual(response.data['super_admin_name'], 'Gamma Super Admin')
        self.assertEqual(response.data['academic_terms_type'], 'year')
        self.assertEqual(response.data['academic_terms'][0], '1st Year')

    def test_create_accepts_legacy_name_alias(self):
        response = self.client.post(
            '/institutes/institute/',
            data={
                'name': 'Delta Institute',
                'super_admin_name': 'Delta Super Admin',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['institute_name'], 'Delta Institute')
        self.assertEqual(response.data['name'], 'Delta Institute')
        self.assertEqual(response.data['super_admin_name'], 'Delta Super Admin')
        self.assertEqual(response.data['academic_terms_type'], 'semester')
        self.assertEqual(response.data['academic_terms'][0], '1st Semester')

    def test_academic_terms_action_returns_lightweight_payload(self):
        response = self.client.get(f'/institutes/institute/{self.institute.id}/academic-terms/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['name'], self.institute.institute_name)
        self.assertEqual(response.data['academic_terms_type'], 'semester')
        self.assertEqual(response.data['academic_terms'][0], '1st Semester')
        self.assertNotIn('students', response.data)

    def test_admin_form_shows_semester_and_year_choices_only(self):
        form = InstituteAdminForm()
        choices = [value for value, _label in form.fields['academic_terms_type'].choices]
        self.assertEqual(choices, ['semester', 'year'])

    def test_sync_institute_academic_terms_updates_related_records(self):
        student = self.institute.students.get(name='Alice')
        course_assignment = student.course_assignments
        term = AcademicTerms.objects.get(branch__course__institute=self.institute, name='Semester 1st')

        Attendance.objects.create(
            student=student,
            date=date(2025, 6, 2),
            class_name='B.Tech',
            branch='CS',
            year_semester='Semester 1st',
            status=True,
        )
        ExamData.objects.create(
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            subject='Physics',
            exam_type='Midterm',
            total_marks=100,
        )
        weekly_day = WeeklyScheduleDay.objects.create(institute=self.institute, day='Monday')
        WeeklyScheduleData.objects.create(
            weekly_schedule_day=weekly_day,
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            start_time=time(9, 0),
            end_time=time(10, 0),
            subject='Physics',
            room_number='101',
            professor='Dr Bob',
        )
        exam_date = ExamScheduleDate.objects.create(institute=self.institute, date=date(2025, 6, 10))
        ExamScheduleData.objects.create(
            exam_schedule_date=exam_date,
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            start_time=time(11, 0),
            end_time=time(12, 0),
            subject='Physics',
            room_number='102',
            type='Theory',
        )
        PublishedWeeklySchedule.objects.create(
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            schedule_data=[],
            source_hash='weekly',
        )
        PublishedExamSchedule.objects.create(
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            schedule_data=[],
            source_hash='exam',
        )
        published_student = PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=student.id,
            name=student.name,
            student_personal_id='STU-1',
            student_data={
                'course_assignment': {
                    'class_name': 'B.Tech',
                    'branch': 'CS',
                    'academic_term': 'Semester 1st',
                },
            },
            subjects_assigned=[],
        )
        PublishedExamResult.objects.create(
            institute=self.institute,
            published_student=published_student,
            source_student_id=student.id,
            name=student.name,
            student_personal_id='STU-1',
            exam_results=[
                {
                    'subject': 'Physics',
                    'academic_term': 'Semester 1st',
                    'status': 'Pass',
                },
            ],
        )

        self.institute.academic_terms_type = 'year'
        self.institute.save(update_fields=['academic_terms_type'])
        summary = sync_institute_academic_terms(self.institute)

        course_assignment.refresh_from_db()
        term.refresh_from_db()
        attendance = Attendance.objects.get(student=student, date=date(2025, 6, 2))
        exam_data = ExamData.objects.get(institute=self.institute, subject='Physics')
        weekly_schedule = WeeklyScheduleData.objects.get(institute=self.institute, subject='Physics')
        exam_schedule = ExamScheduleData.objects.get(institute=self.institute, subject='Physics')
        published_weekly = PublishedWeeklySchedule.objects.get(institute=self.institute)
        published_exam = PublishedExamSchedule.objects.get(institute=self.institute)
        published_student.refresh_from_db()
        published_exam_result = PublishedExamResult.objects.get(institute=self.institute)

        self.assertGreater(summary['total_updates'], 0)
        self.assertEqual(course_assignment.academic_term, '1st Year')
        self.assertEqual(term.name, '1st Year')
        self.assertEqual(attendance.year_semester, '1st Year')
        self.assertEqual(exam_data.academic_term, '1st Year')
        self.assertEqual(weekly_schedule.academic_term, '1st Year')
        self.assertEqual(exam_schedule.academic_term, '1st Year')
        self.assertEqual(published_weekly.academic_term, '1st Year')
        self.assertEqual(published_exam.academic_term, '1st Year')
        self.assertEqual(
            published_student.student_data['course_assignment']['academic_term'],
            '1st Year',
        )
        self.assertEqual(
            published_exam_result.exam_results[0]['academic_term'],
            '1st Year',
        )
