from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from professors.models import (
    Professor,
    ProfessorExperience,
    ProfessorQualification,
    professorAdminEmployement,
)

from .models import ProfessorAttendance, ProfessorLeave


class ProfessorAttendanceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Alpha Institute',
            admin_key='a' * 32,
        )
        self.other_institute = Institute.objects.create(
            name='Beta Institute',
            admin_key='b' * 32,
        )

        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Bob',
            email='bob@example.com',
            phone_number='9999999999',
        )
        ProfessorExperience.objects.create(
            professor=self.professor,
            department='CSE',
        )
        ProfessorQualification.objects.create(
            professor=self.professor,
            specialization='Artificial Intelligence',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='PROF-1',
            employee_id='EMP-1',
        )

        self.other_professor = Professor.objects.create(
            institute=self.other_institute,
            name='Dr Eve',
            email='eve@example.com',
            phone_number='8888888888',
        )
        ProfessorExperience.objects.create(
            professor=self.other_professor,
            department='ECE',
        )
        ProfessorQualification.objects.create(
            professor=self.other_professor,
            specialization='Embedded Systems',
        )
        professorAdminEmployement.objects.create(
            professor=self.other_professor,
            personal_id='PROF-2',
            employee_id='EMP-2',
        )

    def test_professor_directory_returns_required_fields(self):
        response = self.client.get(
            f'/professor_attendance/professors/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['name'], 'Dr Bob')
        self.assertEqual(response.data[0]['department'], 'CSE')
        self.assertEqual(response.data[0]['email'], 'bob@example.com')
        self.assertEqual(response.data[0]['phone_number'], '9999999999')
        self.assertEqual(response.data[0]['specialization'], 'Artificial Intelligence')

    def test_create_professor_attendance_returns_professor_details(self):
        response = self.client.post(
            f'/professor_attendance/attendance/?institute={self.institute.id}',
            data={
                'professor': self.professor.id,
                'date': '2026-03-19',
                'status': True,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['professor_name'], 'Dr Bob')
        self.assertEqual(response.data['department'], 'CSE')
        self.assertEqual(response.data['email'], 'bob@example.com')
        self.assertEqual(response.data['phone_number'], '9999999999')
        self.assertEqual(response.data['specialization'], 'Artificial Intelligence')
        self.assertTrue(response.data['status'])
        self.assertIsNotNone(response.data['attendance_time'])
        self.assertNotIn('present_time', response.data)
        self.assertNotIn('absent_time', response.data)

    def test_professor_attendance_rejects_professor_from_other_institute(self):
        response = self.client.post(
            f'/professor_attendance/attendance/?institute={self.institute.id}',
            data={
                'professor': self.other_professor.id,
                'date': '2026-03-19',
                'status': False,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('professor', response.data)

    def test_create_professor_leave_returns_professor_details(self):
        response = self.client.post(
            f'/professor_attendance/leaves/?institute={self.institute.id}',
            data={
                'professor': self.professor.id,
                'date': '2026-03-20',
                'comment': 'Medical leave',
                'status': 'reject',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['professor_name'], 'Dr Bob')
        self.assertEqual(response.data['department'], 'CSE')
        self.assertEqual(response.data['email'], 'bob@example.com')
        self.assertEqual(response.data['comment'], 'Medical leave')
        self.assertEqual(response.data['status'], 'reject')

    def test_professor_leave_list_filters_by_status(self):
        ProfessorLeave.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 21),
            comment='Conference',
            status=ProfessorLeave.STATUS_APPROVED,
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 22),
            comment='Personal',
            status=ProfessorLeave.STATUS_REJECT,
        )

        response = self.client.get(
            f'/professor_attendance/leaves/?institute={self.institute.id}&status=approved',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['status'], 'approved')

    def test_professor_attendance_list_filters_by_professor(self):
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 23),
            status=True,
        )

        response = self.client.get(
            f'/professor_attendance/attendance/?institute={self.institute.id}&professor={self.professor.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['professor_name'], 'Dr Bob')

    def test_update_professor_attendance_keeps_single_attendance_time_field(self):
        attendance = ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 24),
            status=True,
        )

        self.assertIsNotNone(attendance.attendance_time)

        response = self.client.patch(
            f'/professor_attendance/attendance/{attendance.id}/?institute={self.institute.id}',
            data={'status': False},
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        attendance.refresh_from_db()
        self.assertFalse(attendance.status)
        self.assertIsNotNone(attendance.attendance_time)
        self.assertIsNotNone(response.data['attendance_time'])
        self.assertNotIn('present_time', response.data)
        self.assertNotIn('absent_time', response.data)
