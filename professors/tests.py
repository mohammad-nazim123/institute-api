from io import StringIO

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.core.management import call_command
from rest_framework.test import APIClient

from activity_feed.models import ActivityEvent
from attendance.models import AttendanceSubmission
from iinstitutes_list.models import Institute
from payments.models import ProfessorsPayments
from professor_attendance.models import ProfessorAttendance
from professor_leaves.models import ProfessorLeave as PublishedProfessorLeave
from subordinate_access.models import SubordinateAccess

from .models import (
    Professor,
    ProfessorAddress,
    ProfessorExperience,
    ProfessorQualification,
    professorAdminEmployement,
    professorClassAssigned,
)


class ProfessorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Alpha Institute',
            admin_key='a' * 32,
        )
        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Bob',
            email='bob@example.com',
            phone_number='9999999999',
        )
        ProfessorAddress.objects.create(
            professor=self.professor,
            city='Kolkata',
        )
        ProfessorQualification.objects.create(
            professor=self.professor,
            degree='M.Tech',
            institution='IIT',
        )
        ProfessorExperience.objects.create(
            professor=self.professor,
            department='CSE',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='PROF-1',
            employee_id='EMP-1',
        )
        professorClassAssigned.objects.create(
            professor=self.professor,
            assigned_course='B.Tech',
            assigned_section='A',
        )

    def _create_professor(self, name, personal_id, employee_id, department):
        professor = Professor.objects.create(
            institute=self.institute,
            name=name,
            email=f'{employee_id.lower()}@example.com',
            phone_number=f'900000{Professor.objects.count():04d}',
        )
        ProfessorAddress.objects.create(
            professor=professor,
            city='Kolkata',
        )
        ProfessorExperience.objects.create(
            professor=professor,
            department=department,
        )
        professorAdminEmployement.objects.create(
            professor=professor,
            personal_id=personal_id,
            employee_id=employee_id,
        )
        professorClassAssigned.objects.create(
            professor=professor,
            assigned_course='B.Tech',
            assigned_section='A',
        )
        return professor

    def test_list_returns_institute_dictionary(self):
        response = self.client.get(
            f'/professors/professors/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results']['name'], 'Alpha Institute')
        self.assertEqual(response.data['results']['professors'][0]['name'], 'Dr Bob')
        self.assertNotIn('age', response.data['results']['professors'][0])
        self.assertEqual(response.data['page'], 1)

    def test_list_uses_four_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/professors/professors/?institute={self.institute.id}',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 4)

    def test_list_returns_only_requested_page(self):
        for index in range(2, 12):
            self._create_professor(
                f'Dr Professor {index}',
                f'PROF-{index}',
                f'EMP-{index}',
                'ECE',
            )

        response = self.client.get(
            f'/professors/professors/?institute={self.institute.id}&page=2',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(response.data['page'], 2)
        self.assertEqual(response.data['total_pages'], 2)
        self.assertEqual(response.data['page_size'], 10)
        self.assertEqual(
            [professor['name'] for professor in response.data['results']['professors']],
            ['Dr Professor 11'],
        )

    def test_list_returns_empty_wrapper_instead_of_error_when_no_professors_exist(self):
        Professor.objects.filter(institute=self.institute).delete()

        response = self.client.get(
            f'/professors/professors/?institute={self.institute.id}&page=4',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['results']['name'], 'Alpha Institute')
        self.assertEqual(response.data['results']['professors'], [])

    def test_list_falls_back_to_last_available_page_after_records_are_removed(self):
        response = self.client.get(
            f'/professors/professors/?institute={self.institute.id}&page=9',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(
            [professor['name'] for professor in response.data['results']['professors']],
            ['Dr Bob'],
        )

    def test_list_returns_empty_state_for_out_of_range_page_after_records_are_removed(self):
        Professor.objects.filter(institute=self.institute).delete()

        response = self.client.get(
            f'/professors/professors/?institute={self.institute.id}&page=2',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['total_pages'], 1)
        self.assertEqual(response.data['results']['professors'], [])

    def test_search_filters_by_name_employee_id_and_department(self):
        self._create_professor('Dr Charlie', 'PROF-2', 'EMP-CSE', 'Computer Science')
        self._create_professor('Dr Eve', 'PROF-3', 'EMP-MECH', 'Mechanical')

        test_cases = (
            ('?search=Charlie', ['Dr Charlie']),
            ('?search=EMP-CSE', ['Dr Charlie']),
            ('?search=Mechanical', ['Dr Eve']),
            ('?name=Bob', ['Dr Bob']),
            ('?employee_id=EMP-1', ['Dr Bob']),
            ('?department=CSE', ['Dr Bob']),
        )

        for query_suffix, expected_names in test_cases:
            with self.subTest(query_suffix=query_suffix):
                response = self.client.get(
                    f'/professors/professors/{query_suffix}&institute={self.institute.id}&page_size=10',
                    HTTP_X_ADMIN_KEY=self.institute.admin_key,
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [professor['name'] for professor in response.data['results']['professors']],
                    expected_names,
                )

    def test_retrieve_uses_two_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/professors/professors/{self.professor.id}/',
                HTTP_X_PERSONAL_KEY='PROF-1',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Dr Bob')
        self.assertNotIn('age', response.data)
        self.assertLessEqual(len(queries), 2)

    def test_retrieve_allows_admin_key_without_institute_query(self):
        response = self.client.get(
            f'/professors/professors/{self.professor.id}/',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Dr Bob')
        self.assertEqual(response.data['experience']['department'], 'CSE')

    def test_verify_uses_two_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                '/professors/verify/',
                data={
                    'email': 'bob@example.com',
                    'personal_id': 'PROF-1',
                    'institute_name': self.institute.name,
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Dr Bob')
        self.assertLessEqual(len(queries), 2)

    def test_fetch_by_personal_key_uses_two_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                '/professors/fetch-by-key/',
                data={'personal_id': 'PROF-1'},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Dr Bob')
        self.assertLessEqual(len(queries), 2)

    def test_lookup_professor_id_uses_one_query(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                '/professors/lookup_professor_id/',
                data={
                    'personal_id': 'PROF-1',
                    'institute_name': self.institute.name,
                    'email': 'bob@example.com',
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['professor_id'], self.professor.id)
        self.assertLessEqual(len(queries), 1)

    def test_create_professor_with_nested_data(self):
        response = self.client.post(
            f'/professors/professors/?institute={self.institute.id}',
            data={
                'name': 'Dr Alice',
                'email': 'alice@example.com',
                'phone_number': '8888888888',
                'gender': 'Female',
                'father_name': 'Father Alice',
                'mother_name': 'Mother Alice',
                'indentity_number': 'ID-ALICE',
                'marital_status': 'Single',
                'address': {
                    'city': 'Delhi',
                    'state': 'Delhi',
                    'country': 'India',
                },
                'qualification': [
                    {
                        'degree': 'M.Tech',
                        'institution': 'IIT Delhi',
                        'year_of_passing': '2018',
                        'percentage': '85',
                        'specialization': 'CSE',
                    }
                ],
                'experience': {
                    'designation': 'Associate Professor',
                    'department': 'AI',
                    'teaching_subject': 'ML',
                    'teaching_experience': '6',
                    'interest': 'Research',
                },
                'admin_employement': {
                    'personal_id': 'PROF-ALICE-001',
                    'employee_id': 'EMP-ALICE-001',
                    'employement_type': 'Full Time',
                    'working_hours': '8',
                    'salary': '70000',
                },
                'class_assigned': {
                    'assigned_course': 'M.Tech',
                    'assigned_section': 'B',
                    'assigned_year': '2',
                    'session': '2026-2027',
                },
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['professors'][0]['name'], 'Dr Alice')
        self.assertEqual(response.data['professors'][0]['address']['city'], 'Delhi')
        self.assertEqual(response.data['professors'][0]['experience']['department'], 'AI')
        self.assertEqual(response.data['professors'][0]['admin_employement']['employee_id'], 'EMP-ALICE-001')
        self.assertEqual(Professor.objects.filter(institute=self.institute, name='Dr Alice').count(), 1)

    def test_patch_professor_updates_nested_data(self):
        response = self.client.patch(
            f'/professors/professors/{self.professor.id}/?institute={self.institute.id}',
            data={
                'name': 'Dr Robert',
                'address': {
                    'city': 'Mumbai',
                },
                'qualification': [
                    {
                        'degree': 'PhD',
                        'institution': 'IISc',
                        'year_of_passing': '2022',
                        'percentage': '90',
                        'specialization': 'Data Science',
                    }
                ],
                'experience': {
                    'department': 'Data Science',
                    'interest': 'Deep Learning',
                },
                'admin_employement': {
                    'employee_id': 'EMP-99',
                },
                'class_assigned': {
                    'assigned_section': 'C',
                },
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['professors'][0]['name'], 'Dr Robert')
        self.assertEqual(response.data['professors'][0]['address']['city'], 'Mumbai')
        self.assertEqual(
            response.data['professors'][0]['qualification'][0]['specialization'],
            'Data Science',
        )
        self.assertEqual(
            response.data['professors'][0]['experience']['department'],
            'Data Science',
        )
        self.assertEqual(
            response.data['professors'][0]['admin_employement']['employee_id'],
            'EMP-99',
        )
        self.assertEqual(
            response.data['professors'][0]['class_assigned']['assigned_section'],
            'C',
        )

    def test_delete_professor(self):
        response = self.client.delete(
            f'/professors/professors/{self.professor.id}/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Professor.objects.filter(id=self.professor.id).exists())


class CreateDummyProfessorsCommandTests(TestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Seed Institute',
            admin_key='b' * 32,
        )

    def test_command_creates_requested_professors_with_blank_emails(self):
        output = StringIO()

        call_command(
            'create_dummy_professors',
            '--institute-id',
            str(self.institute.id),
            '--count',
            '50',
            stdout=output,
        )

        self.assertEqual(Professor.objects.filter(institute=self.institute).count(), 50)
        self.assertEqual(
            Professor.objects.filter(institute=self.institute).exclude(email='').count(),
            0,
        )
        self.assertEqual(
            ProfessorExperience.objects.filter(professor__institute=self.institute).count(),
            50,
        )
        self.assertEqual(
            professorAdminEmployement.objects.filter(professor__institute=self.institute).count(),
            50,
        )
        self.assertIn('Created 50 dummy professors', output.getvalue())


class CreateDummyBaHistoryFirstSemesterDemoCommandTests(TestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='History Demo Institute',
            admin_key='c' * 32,
            event_status='active',
        )

    def test_command_creates_one_professor_with_attendance_payments_and_timed_student_submissions(self):
        output = StringIO()

        call_command(
            'create_dummy_ba_history_first_semester_demo',
            '--institute-id',
            str(self.institute.id),
            '--professor-count',
            '1',
            '--student-count',
            '2',
            '--attendance-days',
            '365',
            stdout=output,
        )

        professor = Professor.objects.get(institute=self.institute)

        self.assertEqual(Professor.objects.filter(institute=self.institute).count(), 1)
        self.assertTrue(
            ProfessorAttendance.objects.filter(
                institute=self.institute,
                professor=professor,
            ).exists()
        )
        self.assertEqual(
            ProfessorAttendance.objects.filter(
                institute=self.institute,
                professor=professor,
                attendance_time__isnull=True,
            ).count(),
            0,
        )
        self.assertEqual(
            ProfessorsPayments.objects.filter(
                institute=self.institute,
                professor=professor,
            ).count(),
            12,
        )
        self.assertEqual(
            ProfessorsPayments.objects.filter(
                institute=self.institute,
                professor=professor,
                payment_status='paid',
            ).count(),
            12,
        )
        self.assertTrue(
            PublishedProfessorLeave.objects.filter(
                institute=self.institute,
                published_professor__source_professor_id=professor.id,
            ).exists()
        )
        self.assertGreater(
            AttendanceSubmission.objects.filter(
                institute=self.institute,
                class_name='B.A',
                branch='History',
                year_semester='1st Semester',
                marked_by=professor,
            ).count(),
            0,
        )
        self.assertEqual(
            AttendanceSubmission.objects.filter(
                institute=self.institute,
                class_name='B.A',
                branch='History',
                year_semester='1st Semester',
                attendance_time__isnull=True,
            ).count(),
            0,
        )
        self.assertTrue(
            SubordinateAccess.objects.filter(
                institute=self.institute,
                access_control='admin access',
                name='Demo Admin Employee',
            ).exists()
        )
        self.assertTrue(
            SubordinateAccess.objects.filter(
                institute=self.institute,
                access_control='fee access',
                name='Demo Fee Employee',
            ).exists()
        )

        activity_events = ActivityEvent.objects.filter(institute=self.institute)
        admin_attendance_event = (
            activity_events
            .filter(actor_access_control='admin access', entity_type='professor attendance')
            .order_by('id')
            .first()
        )
        fee_event = (
            activity_events
            .filter(actor_access_control='fee access', entity_type='student fee')
            .order_by('id')
            .first()
        )

        self.assertIsNotNone(admin_attendance_event)
        self.assertEqual(admin_attendance_event.details['task'], 'take_professor_attendance')
        self.assertIn('present_count', admin_attendance_event.details)
        self.assertIsNotNone(fee_event)
        self.assertIn(
            fee_event.details['task'],
            {'student_fee_ledger_review', 'student_fee_collection'},
        )

        client = APIClient()
        timeline_response = client.get(
            (
                f'/activity_feed/timeline/?institute={self.institute.id}'
                f'&date={admin_attendance_event.occurred_at.date().isoformat()}'
            ),
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(timeline_response.status_code, 200)
        fetched_tasks = {
            item['details'].get('task')
            for item in timeline_response.data['results']['timeline']
        }
        self.assertIn('take_professor_attendance', fetched_tasks)

        self.assertIn('Created 1 dummy professors', output.getvalue())
        self.assertIn('professor payment rows', output.getvalue())
        self.assertIn('activity feed events', output.getvalue())
