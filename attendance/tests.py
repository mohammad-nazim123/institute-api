from datetime import date, timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from students.models import Student, StudentCourseAssignment

from .models import Attendance, AttendanceSubmission


def create_attendance(student, *, date, status, class_name='', branch='', year_semester=''):
    submission, _created = AttendanceSubmission.objects.get_or_create(
        institute=student.institute,
        date=date,
        class_name=class_name,
        branch=branch,
        year_semester=year_semester,
    )
    return Attendance.objects.create(
        student=student,
        submission=submission,
        status=status,
    )


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

        create_attendance(
            student=self.student_one,
            date=date(2026, 3, 28),
            class_name='B.A',
            branch='History',
            year_semester='1st Semester',
            status=True,
        )
        create_attendance(
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
        self.assertIsNotNone(response.data[0]['attendance_records'][0]['attendance_time'])
        self.assertEqual(response.data[1]['name'], 'Sara')
        self.assertFalse(response.data[1]['attendance_records'][0]['status'])
        self.assertIsNotNone(response.data[1]['attendance_records'][0]['attendance_time'])

    def test_bulk_student_attendance_uses_small_fixed_query_count(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/attendance/students/attendance/?institute={self.institute.id}&date=2026-03-28',
                **self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 3)

    def test_mark_attendance_stamps_submission_time(self):
        response = self.client.post(
            f'/attendance/attendance/mark/?institute={self.institute.id}',
            {
                'date': '2026-03-29',
                'class_name': 'B.A',
                'branch': 'History',
                'year_semester': '1st Semester',
                'attendance': [
                    {
                        'student_id': self.student_one.id,
                        'status': True,
                    },
                ],
            },
            format='json',
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['institute_id'], self.institute.id)
        self.assertEqual(response.data['class_name'], 'B.A')
        self.assertEqual(response.data['branch'], 'History')
        self.assertEqual(response.data['year_semester'], '1st Semester')
        self.assertIn('attendance_time', response.data)
        self.assertIn('submitted_at', response.data)
        self.assertEqual(len(response.data['student_result']), 1)
        self.assertIn('id', response.data['student_result'][0])
        self.assertEqual(response.data['student_result'][0]['student_id'], self.student_one.id)
        self.assertTrue(response.data['student_result'][0]['status'])

        attendance = Attendance.objects.get(
            student=self.student_one,
            submission__date=date(2026, 3, 29),
        )
        self.assertIsNotNone(attendance.attendance_time)
        self.assertIsNotNone(attendance.submitted_at)
        self.assertEqual(attendance.class_name, 'B.A')
        self.assertEqual(attendance.branch, 'History')
        self.assertEqual(attendance.year_semester, '1st Semester')


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


class AttendanceStudentSummaryViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Attendance Summary Institute',
            admin_key='g' * 32,
            event_status='active',
        )
        self.headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        self.student_one = Student.objects.create(
            institute=self.institute,
            name='Summary Student One',
            gender='Female',
            category='General',
        )
        self.student_two = Student.objects.create(
            institute=self.institute,
            name='Summary Student Two',
            gender='Male',
            category='OBC',
        )

        create_attendance(
            student=self.student_one,
            date=date(2026, 3, 5),
            status=True,
        )
        create_attendance(
            student=self.student_one,
            date=date(2026, 3, 6),
            status=False,
        )
        create_attendance(
            student=self.student_one,
            date=date(2026, 4, 1),
            status=True,
        )

    def test_student_attendance_summary_returns_monthly_counts_without_daily_records(self):
        response = self.client.get(
            f'/attendance/attendance/students/summary/?institute={self.institute.id}'
            f'&month=2026-03&student_ids={self.student_one.id},{self.student_two.id}',
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {
                    'student_id': self.student_one.id,
                    'present': 1,
                    'absent': 1,
                    'total': 2,
                    'percentage': 50,
                },
                {
                    'student_id': self.student_two.id,
                    'present': 0,
                    'absent': 0,
                    'total': 0,
                    'percentage': 0,
                },
            ],
        )


class AttendanceRecordCrudViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Attendance CRUD Institute',
            admin_key='c' * 32,
            event_status='active',
        )
        self.headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }
        self.student = Student.objects.create(
            institute=self.institute,
            name='CRUD Student',
            gender='Female',
            category='General',
        )

    def test_attendance_record_list_filters_by_student_ids(self):
        second_student = Student.objects.create(
            institute=self.institute,
            name='Second CRUD Student',
            gender='Male',
            category='General',
        )
        third_student = Student.objects.create(
            institute=self.institute,
            name='Third CRUD Student',
            gender='Female',
            category='General',
        )
        create_attendance(
            student=self.student,
            date=date(2026, 4, 2),
            class_name='B.A',
            branch='History',
            year_semester='1st Semester',
            status=True,
        )
        create_attendance(
            student=second_student,
            date=date(2026, 4, 2),
            class_name='B.A',
            branch='History',
            year_semester='1st Semester',
            status=False,
        )
        create_attendance(
            student=third_student,
            date=date(2026, 4, 2),
            class_name='B.A',
            branch='History',
            year_semester='1st Semester',
            status=True,
        )

        response = self.client.get(
            (
                f'/attendance/attendance/records/?institute={self.institute.id}'
                f'&student_ids={self.student.id},{second_student.id}&year=2026'
            ),
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        returned_student_ids = sorted(
            attendance['student_id']
            for submission in response.data
            for attendance in submission['student_result']
        )
        self.assertEqual(returned_student_ids, [self.student.id, second_student.id])

    def test_attendance_record_crud_lifecycle(self):
        create_response = self.client.post(
            f'/attendance/attendance/records/?institute={self.institute.id}',
            {
                'student': self.student.id,
                'date': '2026-04-02',
                'class_name': 'B.A',
                'branch': 'History',
                'year_semester': '1st Semester',
                'status': True,
            },
            format='json',
            **self.headers,
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertIn('attendance_time', create_response.data)
        self.assertIn('submitted_at', create_response.data)
        self.assertEqual(create_response.data['institute_id'], self.institute.id)
        self.assertEqual(create_response.data['class_name'], 'B.A')
        self.assertEqual(len(create_response.data['student_result']), 1)
        record_id = create_response.data['student_result'][0]['id']
        self.assertEqual(
            create_response.data['student_result'][0]['student_id'],
            self.student.id,
        )

        attendance = Attendance.objects.get(pk=record_id)
        old_submitted_at = timezone.now() - timedelta(days=1)
        attendance.submission.submitted_at = old_submitted_at
        attendance.submission.save(update_fields=['submitted_at'])

        list_response = self.client.get(
            f'/attendance/attendance/records/?institute={self.institute.id}&student_id={self.student.id}&date=2026-04-02',
            **self.headers,
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['id'], attendance.submission_id)
        self.assertIn('attendance_time', list_response.data[0])
        self.assertEqual(list_response.data[0]['student_result'][0]['id'], record_id)

        retrieve_response = self.client.get(
            f'/attendance/attendance/records/{record_id}/?institute={self.institute.id}',
            **self.headers,
        )

        self.assertEqual(retrieve_response.status_code, 200)
        self.assertIn('attendance_time', retrieve_response.data)
        self.assertEqual(retrieve_response.data['student_result'][0]['id'], record_id)

        student_history_response = self.client.get(
            f'/attendance/attendance/student/{self.student.id}/?institute={self.institute.id}&date=2026-04-02',
            **self.headers,
        )

        self.assertEqual(student_history_response.status_code, 200)
        self.assertEqual(len(student_history_response.data), 1)
        self.assertIsNotNone(student_history_response.data[0]['attendance_time'])

        update_response = self.client.patch(
            f'/attendance/attendance/records/{record_id}/?institute={self.institute.id}',
            {'status': False},
            format='json',
            **self.headers,
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertIn('attendance_time', update_response.data)
        self.assertFalse(update_response.data['student_result'][0]['status'])

        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.attendance_time)
        self.assertGreater(attendance.submitted_at, old_submitted_at)

        delete_response = self.client.delete(
            f'/attendance/attendance/records/{record_id}/?institute={self.institute.id}',
            **self.headers,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertIn('attendance_time', delete_response.data)
        self.assertEqual(delete_response.data['student_result'][0]['id'], record_id)
        self.assertFalse(Attendance.objects.filter(pk=record_id).exists())
