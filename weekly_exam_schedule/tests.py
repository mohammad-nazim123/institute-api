from datetime import date, time

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute

from .models import (
    ExamScheduleData,
    ExamScheduleDate,
    WeeklyScheduleData,
    WeeklyScheduleDay,
)


class WeeklyExamScheduleApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='My Institute',
            admin_key='a' * 32,
        )
        self.auth_headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        self.weekly_day = WeeklyScheduleDay.objects.create(
            institute=self.institute,
            day='Monday',
        )
        WeeklyScheduleData.objects.create(
            weekly_schedule_day=self.weekly_day,
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            start_time=time(10, 0),
            end_time=time(10, 50),
            subject='Machine Learning',
            room_number='Room 101',
            professor='Mohammad Miraj',
        )

        self.exam_date = ExamScheduleDate.objects.create(
            institute=self.institute,
            date=date(2026, 3, 25),
        )
        ExamScheduleData.objects.create(
            exam_schedule_date=self.exam_date,
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            start_time=time(11, 0),
            end_time=time(13, 0),
            subject='Machine Learning',
            room_number='Hall 2',
            type='Midterm',
        )

    def _query(self):
        return (
            f'?institute={self.institute.id}'
            '&class_name=B.Tech&branch=CS&academic_term=Semester 1st'
        )

    def test_dictionary_get_returns_flat_dictionary_format(self):
        response = self.client.get(
            f'/weekly_exam_schedule/{self._query()}',
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['instutes'], 'My Institute')
        self.assertEqual(response.data['class'], 'B.Tech')
        self.assertEqual(response.data['branch'], 'CS')
        self.assertEqual(response.data['acedemic_terms'], '1st Semester')
        self.assertEqual(response.data['Weekly_schedule'][0]['day'], 'Monday')
        self.assertEqual(response.data['exam_schedule'][0]['date'], '2026-03-25')

    def test_dictionary_get_uses_three_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/weekly_exam_schedule/{self._query()}',
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 3)

    def test_weekly_crud_returns_dictionary_format(self):
        create_response = self.client.post(
            f'/weekly_exam_schedule/weekly/?institute={self.institute.id}',
            data={
                'class_name': 'B.Tech',
                'branch': 'CS',
                'academic_term': 'Semester 1st',
                'day': 'Tuesday',
                'weekly_schedule_data': [
                    {
                        'start_time': '12:00:00',
                        'end_time': '12:50:00',
                        'subject': 'Operating Systems',
                        'room_number': 'Room 202',
                        'professor': 'Dr. Khan',
                    }
                ],
            },
            format='json',
            **self.auth_headers,
        )

        self.assertEqual(create_response.status_code, 200)
        created_day = next(
            item for item in create_response.data['Weekly_schedule']
            if item['day'] == 'Tuesday'
        )
        self.assertEqual(created_day['weekly_schedule_data'][0]['subject'], 'Operating Systems')

        update_response = self.client.patch(
            f'/weekly_exam_schedule/weekly/{self.weekly_day.id}/?institute={self.institute.id}',
            data={
                'class_name': 'B.Tech',
                'branch': 'CS',
                'academic_term': 'Semester 1st',
                'day': 'Monday',
                'weekly_schedule_data': [
                    {
                        'start_time': '10:30:00',
                        'end_time': '11:20:00',
                        'subject': 'Deep Learning',
                        'room_number': 'Room 103',
                        'professor': 'Mohammad Miraj',
                    }
                ],
            },
            format='json',
            **self.auth_headers,
        )

        self.assertEqual(update_response.status_code, 200)
        monday = next(
            item for item in update_response.data['Weekly_schedule']
            if item['day'] == 'Monday'
        )
        self.assertEqual(monday['weekly_schedule_data'][0]['subject'], 'Deep Learning')

        delete_response = self.client.delete(
            f'/weekly_exam_schedule/weekly/{self.weekly_day.id}/?institute={self.institute.id}',
            **self.auth_headers,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(
            any(item['id'] == self.weekly_day.id for item in delete_response.data['Weekly_schedule'])
        )

    def test_partial_weekly_update_preserves_existing_schedule_data(self):
        response = self.client.patch(
            f'/weekly_exam_schedule/weekly/{self.weekly_day.id}/?institute={self.institute.id}',
            data={
                'class_name': 'B.Tech',
                'branch': 'CS',
                'academic_term': 'Semester 1st',
                'day': 'Tuesday',
            },
            format='json',
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        weekly_entry = next(
            item for item in response.data['Weekly_schedule']
            if item['id'] == self.weekly_day.id
        )
        self.assertEqual(weekly_entry['day'], 'Tuesday')
        self.assertEqual(len(weekly_entry['weekly_schedule_data']), 1)
        self.assertEqual(
            weekly_entry['weekly_schedule_data'][0]['subject'],
            'Machine Learning',
        )

    def test_exam_crud_returns_dictionary_format(self):
        create_response = self.client.post(
            f'/weekly_exam_schedule/exam/?institute={self.institute.id}',
            data={
                'class_name': 'B.Tech',
                'branch': 'CS',
                'academic_term': 'Semester 1st',
                'date': '2026-04-01',
                'exam_schedule_data': [
                    {
                        'start_time': '09:00:00',
                        'end_time': '12:00:00',
                        'subject': 'Data Structures',
                        'room_number': 'Hall 1',
                        'type': 'Final',
                    }
                ],
            },
            format='json',
            **self.auth_headers,
        )

        self.assertEqual(create_response.status_code, 200)
        created_exam = next(
            item for item in create_response.data['exam_schedule']
            if item['date'] == '2026-04-01'
        )
        self.assertEqual(created_exam['exam_schedule_data'][0]['subject'], 'Data Structures')
