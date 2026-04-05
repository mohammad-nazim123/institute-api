from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from activity_feed.models import ActivityEvent
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

        self.second_professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Alice',
            email='alice@example.com',
            phone_number='7777777777',
        )
        ProfessorExperience.objects.create(
            professor=self.second_professor,
            department='Mathematics',
        )
        ProfessorQualification.objects.create(
            professor=self.second_professor,
            specialization='Applied Mathematics',
        )
        professorAdminEmployement.objects.create(
            professor=self.second_professor,
            personal_id='PROF-3',
            employee_id='EMP-3',
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

        activity = ActivityEvent.objects.get(
            institute=self.institute,
            entity_type='professor attendance',
            action='create',
            entity_id=response.data['id'],
        )
        self.assertEqual(activity.entity_name, 'Dr Bob')
        self.assertIsNotNone(activity.occurred_at)

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

    def test_duplicate_professor_attendance_returns_clear_message(self):
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 19),
            status=True,
        )

        response = self.client.post(
            f'/professor_attendance/attendance/?institute={self.institute.id}',
            data={
                'professor': self.professor.id,
                'date': '2026-03-19',
                'status': False,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['non_field_errors'][0],
            'Attendance already exists for this professor on this date.',
        )

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

    def test_professor_leave_list_filters_by_professor_id_and_month_year(self):
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
            date=date(2026, 4, 2),
            comment='Medical',
            status=ProfessorLeave.STATUS_APPROVED,
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            professor=self.second_professor,
            date=date(2026, 3, 23),
            comment='Workshop',
            status=ProfessorLeave.STATUS_REJECT,
        )

        response = self.client.get(
            f'/professor_attendance/leaves/?institute={self.institute.id}'
            f'&professor_id={self.professor.id}&month=3&year=2026',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['professor'], self.professor.id)
        self.assertEqual(response.data[0]['professor_name'], 'Dr Bob')
        self.assertEqual(response.data[0]['date'], '2026-03-21')

    def test_professor_leave_list_filters_by_professor_id_and_compact_month(self):
        ProfessorLeave.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 25),
            comment='Exam duty',
            status=ProfessorLeave.STATUS_APPROVED,
        )

        response = self.client.get(
            f'/professor_attendance/leaves/?institute={self.institute.id}'
            f'&professor_id={self.professor.id}&month=2026-03',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['date'], '2026-03-25')

    def test_duplicate_professor_leave_returns_clear_message(self):
        ProfessorLeave.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 20),
            comment='Existing leave',
            status=ProfessorLeave.STATUS_APPROVED,
        )

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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['non_field_errors'][0],
            'Leave already exists for this professor on this date.',
        )

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
