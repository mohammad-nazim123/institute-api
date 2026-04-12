from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from activity_feed.models import ActivityEvent
from iinstitutes_list.models import Institute

from .models import (
    Student,
    StudentAdmissionDetails,
    StudentCourseAssignment,
    StudentSystemDetails,
    SubjectsAssigned,
)


class StudentPatchResponseTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='My Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.student = Student.objects.create(
            institute=self.institute,
            name='Nazia Khan',
            gender='Female',
        )

    def test_patch_response_keeps_institute_wrapper(self):
        response = self.client.patch(
            f"{reverse('students-detail', args=[self.student.id])}?institute={self.institute.id}",
            {'identity': '5456677889988'},
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['name'], self.institute.name)
        self.assertEqual(len(response.data['students']), 1)
        self.assertEqual(response.data['students'][0]['id'], self.student.id)
        self.assertEqual(response.data['students'][0]['identity'], '5456677889988')

    def test_patch_updates_start_class_date_in_admission_details(self):
        StudentAdmissionDetails.objects.create(student=self.student)

        response = self.client.patch(
            f"{reverse('students-detail', args=[self.student.id])}?institute={self.institute.id}",
            {
                'admission_details': {
                    'start_class_date': '2026-04-01',
                    'academic_year': '2026-2027',
                },
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        admission_details = self.student.admission_details
        admission_details.refresh_from_db()
        self.assertEqual(admission_details.start_class_date.isoformat(), '2026-04-01')
        self.assertEqual(admission_details.academic_year, '2026-2027')


class StudentPermissionTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Permission Institute',
            admin_key='b' * 32,
            event_status='active',
        )
        self.student = Student.objects.create(
            institute=self.institute,
            name='Aman Kumar',
        )
        StudentSystemDetails.objects.create(
            student=self.student,
            student_personal_id='STUDENT-0000001',
        )

    def test_students_list_requires_admin_key(self):
        response = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}",
            HTTP_X_PERSONAL_KEY='STUDENT-0000001',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_retrieve_accepts_15_char_personal_key(self):
        response = self.client.get(
            f"{reverse('students-detail', args=[self.student.id])}?institute={self.institute.id}",
            HTTP_X_PERSONAL_KEY='STUDENT-0000001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.student.id)

    def test_student_retrieve_accepts_admin_key_without_institute_query_param(self):
        response = self.client.get(
            reverse('students-detail', args=[self.student.id]),
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.student.id)

    def test_student_retrieve_rejects_non_15_char_personal_key(self):
        response = self.client.get(
            f"{reverse('students-detail', args=[self.student.id])}?institute={self.institute.id}",
            HTTP_X_PERSONAL_KEY='SHORTKEY',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StudentPaginationTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Pagination Institute',
            admin_key='c' * 32,
            event_status='active',
        )
        for index in range(30):
            Student.objects.create(
                institute=self.institute,
                name=f'Student {index + 1}',
                gender='Female',
            )

    def test_students_list_returns_twenty_five_students_per_page(self):
        first_page = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}&page=1",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(first_page.data['count'], 30)
        self.assertEqual(len(first_page.data['results']), 1)
        self.assertEqual(len(first_page.data['results'][0]['students']), 25)

        second_page = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}&page=2",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(second_page.data['count'], 30)
        self.assertEqual(len(second_page.data['results']), 1)
        self.assertEqual(len(second_page.data['results'][0]['students']), 5)

    def test_students_list_filters_by_class_branch_and_academic_term(self):
        matching_ids = []
        for index in range(4):
            student = Student.objects.create(
                institute=self.institute,
                name=f'BA History Student {index + 1}',
                gender='Female',
            )
            StudentCourseAssignment.objects.create(
                student=student,
                class_name='B.A',
                branch='History',
                academic_term='1st Semester',
            )
            matching_ids.append(student.id)

        other_student = Student.objects.create(
            institute=self.institute,
            name='Other Student',
            gender='Male',
        )
        StudentCourseAssignment.objects.create(
            student=other_student,
            class_name='B.Sc',
            branch='Physics',
            academic_term='1st Semester',
        )

        response = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}"
            "&class_name=B.A&branch=History&academic_term=1st Semester&page=1&page_size=3",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(len(response.data['results'][0]['students']), 3)
        response_ids = [student['id'] for student in response.data['results'][0]['students']]
        self.assertEqual(response_ids, matching_ids[:3])

        second_page = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}"
            "&class_name=B.A&branch=History&academic_term=1st Semester&page=2&page_size=3",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(second_page.data['count'], 4)
        self.assertEqual(len(second_page.data['results']), 1)
        self.assertEqual(len(second_page.data['results'][0]['students']), 1)
        self.assertEqual(second_page.data['results'][0]['students'][0]['id'], matching_ids[3])

    def test_students_list_accepts_page_size_query_param(self):
        response = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}&page=1&page_size=10",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results'][0]['students']), 10)

    def test_students_list_returns_empty_wrapper_instead_of_error_when_no_rows_exist(self):
        Student.objects.filter(institute=self.institute).delete()

        response = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}&page=3",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['results'][0]['id'], self.institute.id)
        self.assertEqual(response.data['results'][0]['name'], self.institute.name)
        self.assertEqual(response.data['results'][0]['students'], [])

    def test_students_list_falls_back_to_last_available_page_after_deletes(self):
        response = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}&page=9&page_size=25",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 30)
        self.assertEqual(len(response.data['results'][0]['students']), 5)

    def test_students_list_returns_empty_state_for_out_of_range_page_after_records_are_removed(self):
        Student.objects.filter(institute=self.institute).delete()

        response = self.client.get(
            f"{reverse('students-list')}?institute={self.institute.id}&page=2",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertIsNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['students'], [])


class StudentPerformanceTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Performance Institute',
            admin_key='e' * 32,
            event_status='active',
        )
        for index in range(30):
            Student.objects.create(
                institute=self.institute,
                name=f'Perf Student {index + 1}',
                gender='Female',
                identity=f'ID-{index + 1}',
            )

    def test_students_list_uses_three_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f"{reverse('students-list')}?institute={self.institute.id}",
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 30)
        self.assertLessEqual(len(queries), 3)


class SubjectAssignmentDuplicateTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Subject Institute',
            admin_key='d' * 32,
            event_status='active',
        )
        self.student = Student.objects.create(
            institute=self.institute,
            name='Sara Khan',
            gender='Female',
        )
        SubjectsAssigned.objects.create(
            student=self.student,
            subject='Math',
            unit='1',
        )

    def test_single_subject_assignment_rejects_duplicate_subject(self):
        response = self.client.post(
            f"{reverse('subjects-list-create')}?institute={self.institute.id}",
            {
                'student': self.student.id,
                'subject': 'Math',
                'unit': '2',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Subject already assigned for this student.')
        self.assertEqual(SubjectsAssigned.objects.filter(student=self.student).count(), 1)

    def test_bulk_subject_assignment_creates_only_new_subjects_and_reports_duplicates(self):
        response = self.client.post(
            f"{reverse('subjects-list-create')}?institute={self.institute.id}",
            [
                {
                    'student': self.student.id,
                    'subject': 'Math',
                    'unit': '1',
                },
                {
                    'student': self.student.id,
                    'subject': 'Physics',
                    'unit': '2',
                },
            ],
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['created_subjects']), 1)
        self.assertEqual(response.data['created_subjects'][0]['subject'], 'Physics')
        self.assertEqual(response.data['message'], 'Some subjects are already assigned.')
        self.assertEqual(len(response.data['already_assigned']), 1)
        self.assertEqual(response.data['already_assigned'][0]['subject'], 'Math')
        self.assertEqual(SubjectsAssigned.objects.filter(student=self.student).count(), 2)


class SubjectAssignmentPerformanceTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Fast Subject Institute',
            admin_key='f' * 32,
            event_status='active',
        )
        self.url = f"{reverse('subjects-list-create')}?institute={self.institute.id}"

        self.matching_students = []
        for index in range(40):
            student = Student.objects.create(
                institute=self.institute,
                name=f'History Student {index + 1}',
                gender='Female',
            )
            StudentCourseAssignment.objects.create(
                student=student,
                class_name='B.A',
                branch='History',
                academic_term='1st Semester',
            )
            self.matching_students.append(student)

        self.other_student = Student.objects.create(
            institute=self.institute,
            name='Physics Student',
            gender='Male',
        )
        StudentCourseAssignment.objects.create(
            student=self.other_student,
            class_name='B.Sc',
            branch='Physics',
            academic_term='1st Semester',
        )

    def test_assign_subject_by_class_branch_and_academic_term(self):
        SubjectsAssigned.objects.create(
            student=self.matching_students[0],
            subject='Math',
            unit='1',
        )

        response = self.client.post(
            self.url,
            {
                'subject': 'Math',
                'unit': '1',
                'class_name': 'B.A',
                'branch': 'History',
                'academic_term': '1st Semester',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['matched_students'], 40)
        self.assertEqual(response.data['created_count'], 39)
        self.assertEqual(response.data['already_assigned_count'], 1)
        self.assertEqual(response.data['message'], 'Some subjects are already assigned.')
        self.assertEqual(
            SubjectsAssigned.objects.filter(subject='Math', student__in=self.matching_students).count(),
            40,
        )
        self.assertEqual(ActivityEvent.objects.count(), 1)

    def test_bulk_subject_assignment_uses_small_fixed_query_count(self):
        payload = [
            {
                'student': student.id,
                'subject': 'Physics',
                'unit': '2',
            }
            for student in self.matching_students
        ]

        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                self.url,
                payload,
                format='json',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_count'], 40)
        self.assertEqual(ActivityEvent.objects.count(), 1)
        self.assertLessEqual(len(queries), 6)

    def test_hierarchy_subject_assignment_uses_small_fixed_query_count(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                self.url,
                {
                    'subject': 'Chemistry',
                    'unit': '3',
                    'class_name': 'B.A',
                    'branch': 'History',
                    'academic_term': '1st Semester',
                },
                format='json',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_count'], 40)
        self.assertEqual(ActivityEvent.objects.count(), 1)
        self.assertLessEqual(len(queries), 6)
