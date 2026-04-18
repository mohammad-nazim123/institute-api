from datetime import date, time

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from published_schedules.models import PublishedExamSchedule, PublishedWeeklySchedule
from professors.models import Professor
from syllabus.models import AcademicTerms, Branch, Course, Subject

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


class WeeklyExamScheduleBulkApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Bulk Institute',
            admin_key='b' * 32,
        )
        self.auth_headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        # Context 1: B.Tech / CS / Semester 1st
        self.weekly_day_cs = WeeklyScheduleDay.objects.create(
            institute=self.institute,
            day='Monday',
        )
        WeeklyScheduleData.objects.create(
            weekly_schedule_day=self.weekly_day_cs,
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            start_time=time(9, 0),
            end_time=time(9, 50),
            subject='Algorithms',
            room_number='Room 1',
            professor='Prof A',
        )

        # Context 2: B.Tech / EE / Semester 1st (different branch)
        self.weekly_day_ee = WeeklyScheduleDay.objects.create(
            institute=self.institute,
            day='Tuesday',
        )
        WeeklyScheduleData.objects.create(
            weekly_schedule_day=self.weekly_day_ee,
            institute=self.institute,
            class_name='B.Tech',
            branch='EE',
            academic_term='Semester 1st',
            start_time=time(10, 0),
            end_time=time(10, 50),
            subject='Circuit Theory',
            room_number='Lab 2',
            professor='Prof B',
        )

        # Exam for Context 1
        self.exam_date_cs = ExamScheduleDate.objects.create(
            institute=self.institute,
            date=date(2026, 5, 10),
        )
        ExamScheduleData.objects.create(
            exam_schedule_date=self.exam_date_cs,
            institute=self.institute,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
            start_time=time(10, 0),
            end_time=time(13, 0),
            subject='Algorithms',
            room_number='Hall 1',
            type='Final',
        )

    def test_bulk_get_returns_all_contexts(self):
        response = self.client.get(
            f'/weekly_exam_schedule/bulk/?institute={self.institute.id}',
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        schedules = response.data['schedules']
        # Two distinct contexts: CS and EE
        self.assertEqual(len(schedules), 2)

        branches = {s['branch'] for s in schedules}
        self.assertIn('CS', branches)
        self.assertIn('EE', branches)

        cs_schedule = next(s for s in schedules if s['branch'] == 'CS')
        self.assertEqual(cs_schedule['class'], 'B.Tech')
        self.assertEqual(len(cs_schedule['Weekly_schedule']), 1)
        self.assertEqual(cs_schedule['Weekly_schedule'][0]['day'], 'Monday')
        self.assertEqual(len(cs_schedule['exam_schedule']), 1)
        self.assertEqual(cs_schedule['exam_schedule'][0]['date'], '2026-05-10')

        ee_schedule = next(s for s in schedules if s['branch'] == 'EE')
        self.assertEqual(len(ee_schedule['Weekly_schedule']), 1)
        self.assertEqual(ee_schedule['exam_schedule'], [])

    def test_bulk_get_uses_three_queries_or_fewer(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/weekly_exam_schedule/bulk/?institute={self.institute.id}',
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        # Expected: 1 auth query + 1 weekly query + 1 exam query = 3 total
        self.assertLessEqual(len(queries), 3)

    def test_bulk_get_empty_institute_returns_empty_list(self):
        empty_institute = Institute.objects.create(
            name='Empty Institute',
            admin_key='c' * 32,
        )
        response = self.client.get(
            f'/weekly_exam_schedule/bulk/?institute={empty_institute.id}',
            HTTP_X_ADMIN_KEY=empty_institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['schedules'], [])


class WeeklyExamScheduleReferencesApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Reference Institute',
            admin_key='d' * 32,
        )
        self.auth_headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        course = Course.objects.create(
            institute=self.institute,
            name='B.Tech',
        )
        branch = Branch.objects.create(
            course=course,
            name='CS',
        )
        term = AcademicTerms.objects.create(
            branch=branch,
            name='1st Semester',
        )
        Subject.objects.create(
            academic_terms=term,
            name='Algorithms',
            unit=4,
        )

        Professor.objects.create(
            institute=self.institute,
            name='Dr Alice',
            email='alice@example.com',
            phone_number='9999999998',
        )

    def test_references_get_returns_courses_and_professors(self):
        response = self.client.get(
            f'/weekly_exam_schedule/references/?institute={self.institute.id}',
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['courses'][0]['name'], 'B.Tech')
        self.assertEqual(response.data['courses'][0]['branches'][0]['name'], 'CS')
        self.assertEqual(
            response.data['courses'][0]['branches'][0]['academic_terms'][0]['subjects'][0]['name'],
            'Algorithms',
        )
        self.assertEqual(response.data['professors'], [{
            'id': response.data['professors'][0]['id'],
            'name': 'Dr Alice',
        }])

    def test_references_get_uses_six_queries_or_fewer(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/weekly_exam_schedule/references/?institute={self.institute.id}',
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 6)

    def test_references_get_empty_institute_returns_empty_lists(self):
        empty_institute = Institute.objects.create(
            name='Empty Reference Institute',
            admin_key='e' * 32,
        )

        response = self.client.get(
            f'/weekly_exam_schedule/references/?institute={empty_institute.id}',
            HTTP_X_ADMIN_KEY=empty_institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            'courses': [],
            'professors': [],
        })


class WeeklyExamScheduleWorkspaceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Workspace Institute',
            admin_key='f' * 32,
        )
        self.auth_headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        weekly_day = WeeklyScheduleDay.objects.create(
            institute=self.institute,
            day='Monday',
        )
        WeeklyScheduleData.objects.create(
            weekly_schedule_day=weekly_day,
            institute=self.institute,
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
            start_time=time(9, 0),
            end_time=time(9, 50),
            subject='Ancient History',
            room_number='Room 12',
            professor='Dr Rao',
        )

        exam_date = ExamScheduleDate.objects.create(
            institute=self.institute,
            date=date(2026, 5, 12),
        )
        ExamScheduleData.objects.create(
            exam_schedule_date=exam_date,
            institute=self.institute,
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
            start_time=time(11, 0),
            end_time=time(13, 0),
            subject='Modern History',
            room_number='Hall A',
            type='Midterm',
        )

        self.published_weekly = PublishedWeeklySchedule.objects.create(
            institute=self.institute,
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
            schedule_data=[
                {
                    'id': 41,
                    'day': 'Monday',
                    'weekly_schedule_data': [
                        {
                            'id': 71,
                            'start_time': '09:00:00',
                            'end_time': '09:50:00',
                            'subject': 'Ancient History',
                            'room_number': 'Room 12',
                            'professor': 'Dr Rao',
                        },
                    ],
                },
            ],
        )
        self.published_exam = PublishedExamSchedule.objects.create(
            institute=self.institute,
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
            schedule_data=[
                {
                    'id': 51,
                    'date': '2026-05-12',
                    'exam_schedule_data': [
                        {
                            'id': 81,
                            'start_time': '11:00:00',
                            'end_time': '13:00:00',
                            'subject': 'Modern History',
                            'room_number': 'Hall A',
                            'type': 'Midterm',
                        },
                    ],
                },
            ],
        )

    def _query(self):
        return (
            f'?institute={self.institute.id}'
            '&class_name=B.A&branch=History&academic_term=1st Semester'
        )

    def test_workspace_get_returns_source_and_published_data(self):
        response = self.client.get(
            f'/weekly_exam_schedule/workspace/{self._query()}',
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['class_name'], 'B.A')
        self.assertEqual(response.data['branch'], 'History')
        self.assertEqual(response.data['academic_term'], '1st Semester')
        self.assertEqual(response.data['weekly_schedule'][0]['day'], 'Monday')
        self.assertEqual(response.data['exam_schedule'][0]['date'], '2026-05-12')
        self.assertEqual(response.data['published_weekly_id'], self.published_weekly.id)
        self.assertEqual(response.data['published_exam_id'], self.published_exam.id)
        self.assertEqual(response.data['published_weekly_schedule'], self.published_weekly.schedule_data)
        self.assertEqual(response.data['published_exam_schedule'], self.published_exam.schedule_data)

    def test_workspace_get_empty_or_unpublished_hierarchy_returns_empty_arrays(self):
        response = self.client.get(
            f'/weekly_exam_schedule/workspace/?institute={self.institute.id}'
            '&class_name=B.A&branch=Political Science&academic_term=1st Semester',
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['weekly_schedule'], [])
        self.assertEqual(response.data['exam_schedule'], [])
        self.assertEqual(response.data['published_weekly_schedule'], [])
        self.assertEqual(response.data['published_exam_schedule'], [])
        self.assertIsNone(response.data['published_weekly_id'])
        self.assertIsNone(response.data['published_exam_id'])

    def test_workspace_get_uses_five_queries_or_fewer(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/weekly_exam_schedule/workspace/{self._query()}',
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 5)
