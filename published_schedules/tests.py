from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from students.models import Student, StudentCourseAssignment, StudentSystemDetails
from weekly_exam_schedule.models import (
    ExamScheduleData,
    ExamScheduleDate,
    WeeklyScheduleData,
    WeeklyScheduleDay,
)


class PublishedSchedulesApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='My Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.admin_headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        self.student = Student.objects.create(
            institute=self.institute,
            name='Student One',
        )
        StudentCourseAssignment.objects.create(
            student=self.student,
            class_name='B.Tech',
            branch='CS',
            academic_term='Semester 1st',
        )
        StudentSystemDetails.objects.create(
            student=self.student,
            student_personal_id='STUDENT-0000001',
        )
        self.student_headers = {
            'HTTP_X_PERSONAL_KEY': 'STUDENT-0000001',
        }

        self.weekly_day = WeeklyScheduleDay.objects.create(
            institute=self.institute,
            day='Monday',
        )
        self.weekly_row = WeeklyScheduleData.objects.create(
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
        self.exam_row = ExamScheduleData.objects.create(
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

    def _hierarchy_query(self):
        return (
            f'?institute={self.institute.id}'
            '&class_name=B.Tech&branch=CS&academic_term=Semester 1st'
        )

    def test_weekly_publish_creates_snapshot_and_student_can_read_own_hierarchy(self):
        publish_response = self.client.post(
            f'/institutes/published_schedules/weekly/publish/{self._hierarchy_query()}',
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(
            publish_response.data['message'],
            'Published weekly schedule created successfully.',
        )
        self.assertEqual(publish_response.data['action'], 'created')
        self.assertEqual(len(publish_response.data['weekly_schedule']), 1)

        read_response = self.client.get(
            f'/institutes/published_schedules/weekly/?institute={self.institute.id}',
            **self.student_headers,
        )

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.data['class_name'], 'B.Tech')
        self.assertEqual(len(read_response.data['weekly_schedule']), 1)
        self.assertEqual(read_response.data['weekly_schedule'][0]['day'], 'Monday')

    def test_weekly_publish_returns_already_exists_when_source_is_unchanged(self):
        self.client.post(
            f'/institutes/published_schedules/weekly/publish/{self._hierarchy_query()}',
            format='json',
            **self.admin_headers,
        )

        second_response = self.client.post(
            f'/institutes/published_schedules/weekly/publish/{self._hierarchy_query()}',
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data['message'], 'The data already exist.')

    def test_weekly_publish_updates_snapshot_after_source_changes(self):
        self.client.post(
            f'/institutes/published_schedules/weekly/publish/{self._hierarchy_query()}',
            format='json',
            **self.admin_headers,
        )

        self.weekly_row.subject = 'Deep Learning'
        self.weekly_row.save(update_fields=['subject'])

        update_response = self.client.post(
            f'/institutes/published_schedules/weekly/publish/{self._hierarchy_query()}',
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(
            update_response.data['message'],
            'Published weekly schedule updated successfully.',
        )
        self.assertEqual(update_response.data['action'], 'updated')
        self.assertEqual(
            update_response.data['weekly_schedule'][0]['weekly_schedule_data'][0]['subject'],
            'Deep Learning',
        )

    def test_exam_publish_deletes_snapshot_when_source_is_removed(self):
        create_response = self.client.post(
            f'/institutes/published_schedules/exam/publish/{self._hierarchy_query()}',
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(
            create_response.data['message'],
            'Published exam schedule created successfully.',
        )
        self.assertEqual(create_response.data['action'], 'created')

        self.exam_row.delete()
        self.exam_date.delete()

        republish_response = self.client.post(
            f'/institutes/published_schedules/exam/publish/{self._hierarchy_query()}',
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(republish_response.status_code, 200)
        self.assertEqual(
            republish_response.data['message'],
            'Published exam schedule updated successfully.',
        )
        self.assertEqual(republish_response.data['action'], 'updated')
        self.assertFalse(republish_response.data['exam_schedule'])

    def test_weekly_crud_create_update_delete_requires_admin_key(self):
        create_response = self.client.post(
            f'/institutes/published_schedules/weekly/?institute={self.institute.id}',
            data={
                'class_name': 'B.Tech',
                'branch': 'CS',
                'academic_term': 'Semester 1st',
                'weekly_schedule': [
                    {
                        'id': 999,
                        'day': 'Tuesday',
                        'weekly_schedule_data': [
                            {
                                'id': 1000,
                                'start_time': '12:00:00',
                                'end_time': '12:50:00',
                                'subject': 'Operating Systems',
                                'room_number': 'Room 202',
                                'professor': 'Dr. Khan',
                            }
                        ],
                    }
                ],
            },
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.data['weekly_schedule'][0]['day'], 'Tuesday')
        created_id = create_response.data['published_id']

        update_response = self.client.patch(
            f'/institutes/published_schedules/weekly/{created_id}/?institute={self.institute.id}',
            data={
                'weekly_schedule': [
                    {
                        'id': 999,
                        'day': 'Wednesday',
                        'weekly_schedule_data': [
                            {
                                'id': 1001,
                                'start_time': '01:00:00',
                                'end_time': '01:50:00',
                                'subject': 'Compiler Design',
                                'room_number': 'Room 303',
                                'professor': 'Dr. Sharma',
                            }
                        ],
                    }
                ],
            },
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data['weekly_schedule'][0]['day'], 'Wednesday')

        forbidden_response = self.client.post(
            f'/institutes/published_schedules/weekly/?institute={self.institute.id}',
            data={
                'class_name': 'B.Tech',
                'branch': 'CS',
                'academic_term': 'Semester 1st',
                'weekly_schedule': [],
            },
            format='json',
            **self.student_headers,
        )
        self.assertEqual(forbidden_response.status_code, 403)

        delete_response = self.client.delete(
            f'/institutes/published_schedules/weekly/{created_id}/?institute={self.institute.id}',
            **self.admin_headers,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(delete_response.data['weekly_schedule'])

    def test_exam_crud_create_update_delete_requires_admin_key(self):
        create_response = self.client.post(
            f'/institutes/published_schedules/exam/?institute={self.institute.id}',
            data={
                'class_name': 'B.Tech',
                'branch': 'CS',
                'academic_term': 'Semester 1st',
                'exam_schedule': [
                    {
                        'id': 888,
                        'date': '2026-04-01',
                        'exam_schedule_data': [
                            {
                                'id': 889,
                                'start_time': '09:00:00',
                                'end_time': '12:00:00',
                                'subject': 'Data Structures',
                                'room_number': 'Hall 1',
                                'type': 'Final',
                            }
                        ],
                    }
                ],
            },
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.data['exam_schedule'][0]['date'], '2026-04-01')
        created_id = create_response.data['published_id']

        update_response = self.client.patch(
            f'/institutes/published_schedules/exam/{created_id}/?institute={self.institute.id}',
            data={
                'exam_schedule': [
                    {
                        'id': 888,
                        'date': '2026-04-02',
                        'exam_schedule_data': [
                            {
                                'id': 890,
                                'start_time': '10:00:00',
                                'end_time': '01:00:00',
                                'subject': 'Algorithms',
                                'room_number': 'Hall 3',
                                'type': 'Midterm',
                            }
                        ],
                    }
                ],
            },
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data['exam_schedule'][0]['date'], '2026-04-02')

        forbidden_response = self.client.post(
            f'/institutes/published_schedules/exam/?institute={self.institute.id}',
            data={
                'class_name': 'B.Tech',
                'branch': 'CS',
                'academic_term': 'Semester 1st',
                'exam_schedule': [],
            },
            format='json',
            **self.student_headers,
        )
        self.assertEqual(forbidden_response.status_code, 403)

        delete_response = self.client.delete(
            f'/institutes/published_schedules/exam/{created_id}/?institute={self.institute.id}',
            **self.admin_headers,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(delete_response.data['exam_schedule'])
