from datetime import date

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from students.models import Student, StudentCourseAssignment

from .models import Attendance


class AttendanceBulkViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Attendance Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.other_institute = Institute.objects.create(
            name='Other Institute',
            admin_key='b' * 32,
            event_status='active',
        )
        self.headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        self.student_one = Student.objects.create(
            institute=self.institute,
            name='Aman',
            gender='Male',
            category='General',
        )
        self.student_two = Student.objects.create(
            institute=self.institute,
            name='Sara',
            gender='Female',
            category='OBC',
        )
        Student.objects.create(
            institute=self.other_institute,
            name='Outside Student',
            gender='Male',
            category='General',
        )

        Attendance.objects.create(
            student=self.student_one,
            date=date(2026, 3, 28),
            class_name='B.A',
            branch='History',
            year_semester='1st Semester',
            status=True,
        )
        Attendance.objects.create(
            student=self.student_two,
            date=date(2026, 3, 28),
            class_name='B.A',
            branch='History',
            year_semester='1st Semester',
            status=False,
        )

    def test_bulk_student_attendance_returns_many_students_in_one_response(self):
        response = self.client.get(
            f'/attendance/students/attendance/?institute={self.institute.id}'
            f'&date=2026-03-28&student_ids={self.student_one.id},{self.student_two.id}',
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['name'], 'Aman')
        self.assertEqual(len(response.data[0]['attendance_records']), 1)
        self.assertTrue(response.data[0]['attendance_records'][0]['status'])
        self.assertEqual(response.data[1]['name'], 'Sara')
        self.assertFalse(response.data[1]['attendance_records'][0]['status'])

    def test_bulk_student_attendance_uses_small_fixed_query_count(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/attendance/students/attendance/?institute={self.institute.id}&date=2026-03-28',
                **self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 3)


class AttendanceStudentListViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Attendance Student List Institute',
            admin_key='f' * 32,
            event_status='active',
        )
        self.headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        self.history_student = Student.objects.create(
            institute=self.institute,
            name='History Student',
            gender='Female',
            category='OBC',
        )
        StudentCourseAssignment.objects.create(
            student=self.history_student,
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
        )

        self.physics_student = Student.objects.create(
            institute=self.institute,
            name='Physics Student',
            gender='Male',
            category='General',
        )
        StudentCourseAssignment.objects.create(
            student=self.physics_student,
            class_name='B.Sc',
            branch='Physics',
            academic_term='1st Semester',
        )

    def test_student_list_uses_two_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/attendance/students/?institute={self.institute.id}',
                **self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertLessEqual(len(queries), 2)

    def test_student_list_filters_by_search_and_course_fields(self):
        response = self.client.get(
            f'/attendance/students/?institute={self.institute.id}'
            '&search=History&class_name=B.A&branch=History&academic_term=1st Semester',
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [{
                'id': self.history_student.id,
                'name': 'History Student',
                'gender': 'Female',
                'category': 'OBC',
            }],
        )
