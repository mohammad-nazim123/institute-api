from datetime import date

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

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
        self.assertNotIn('academic_terms_type', payload)
        self.assertNotIn('academic_terms', payload)

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
        self.assertNotIn('academic_terms_type', response.data)
        self.assertNotIn('academic_terms', response.data)
        self.assertLessEqual(len(queries), 8)

    def test_verify_can_return_lightweight_identity_payload(self):
        response = self.client.post(
            '/institutes/verify/',
            data={
                'institute_name': self.institute.institute_name,
                'super_admin_name': self.institute.super_admin_name,
                'admin_key': self.institute.admin_key,
                'include_detail': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['name'], 'Alpha Institute')
        self.assertEqual(response.data['institute_name'], 'Alpha Institute')
        self.assertEqual(response.data['super_admin_name'], 'Primary Super Admin')
        self.assertNotIn('students', response.data)
        self.assertNotIn('professors', response.data)
        self.assertNotIn('courses', response.data)

    def test_summary_retrieve_returns_lightweight_identity_payload(self):
        response = self.client.get(f'/institutes/institute/{self.institute.id}/?summary=1')

        self.assertEqual(response.status_code, 200)
        payload = response.data[0]
        self.assertEqual(payload['id'], self.institute.id)
        self.assertEqual(payload['name'], 'Alpha Institute')
        self.assertEqual(payload['institute_name'], 'Alpha Institute')
        self.assertNotIn('students', payload)
        self.assertNotIn('professors', payload)
        self.assertNotIn('courses', payload)

    def test_summary_list_returns_lightweight_identity_payloads(self):
        response = self.client.get('/institutes/institute/?summary=1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['name'], 'Alpha Institute')
        self.assertNotIn('students', response.data[0])
        self.assertNotIn('professors', response.data[0])
        self.assertNotIn('courses', response.data[0])

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
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['institute_name'], 'Gamma Institute')
        self.assertEqual(response.data['name'], 'Gamma Institute')
        self.assertEqual(response.data['super_admin_name'], 'Gamma Super Admin')
        self.assertNotIn('academic_terms_type', response.data)
        self.assertNotIn('academic_terms', response.data)

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
        self.assertNotIn('academic_terms_type', response.data)
        self.assertNotIn('academic_terms', response.data)
