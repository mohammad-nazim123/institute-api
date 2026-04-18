from datetime import date

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from activity_feed.models import ActivityEvent
from iinstitutes_list.models import Institute
from published_student.models import PublishedStudent
from published_student.views import build_student_snapshot, build_subjects_snapshot

from .models import (
    Student,
    StudentAdmissionDetails,
    StudentContactDetails,
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


class StudentBulkEndpointTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Bulk Status Institute',
            admin_key='g' * 32,
            event_status='active',
        )
        self.url = f"{reverse('students-bulk')}?institute={self.institute.id}"

        self.new_student = self.create_student(
            name='New Student',
            email='new@example.com',
            roll_number='ROLL-NEW',
            enrollment_number='ENR-NEW',
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
            personal_id='BULK-NEW-000001',
            subjects=[('History', '1')],
        )
        self.exist_student = self.create_student(
            name='Existing Student',
            email='exist@example.com',
            roll_number='ROLL-EXIST',
            enrollment_number='ENR-EXIST',
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
            personal_id='BULK-EXIST-0001',
            subjects=[('Economics', '1')],
        )
        self.changed_student = self.create_student(
            name='Changed Student',
            email='changed@example.com',
            roll_number='ROLL-CHANGED',
            enrollment_number='ENR-CHANGED',
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
            personal_id='BULK-CHANGE-0001',
            subjects=[('Political Science', '1')],
        )
        self.subject_changed_student = self.create_student(
            name='Subject Changed Student',
            email='subjects@example.com',
            roll_number='ROLL-SUBJECT',
            enrollment_number='ENR-SUBJECT',
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
            personal_id='BULK-SUBJECT-000',
            subjects=[('Geography', '1')],
        )
        self.other_scope_student = self.create_student(
            name='Other Scope Student',
            email='other@example.com',
            roll_number='ROLL-OTHER',
            enrollment_number='ENR-OTHER',
            class_name='B.Sc',
            branch='Physics',
            academic_term='1st Semester',
            personal_id='BULK-OTHER-00001',
            subjects=[('Physics', '1')],
        )

        self.create_matching_published_snapshot(self.exist_student)
        self.create_changed_published_snapshot(self.changed_student)
        self.create_subject_changed_snapshot(self.subject_changed_student)
        self.create_matching_published_snapshot(self.other_scope_student)

    def create_student(
        self,
        *,
        name,
        email,
        roll_number,
        enrollment_number,
        class_name,
        branch,
        academic_term,
        personal_id,
        subjects,
    ):
        student = Student.objects.create(
            institute=self.institute,
            name=name,
            gender='Female',
            nationality='Indian',
            identity='Aadhar',
            category='General',
        )
        StudentContactDetails.objects.create(
            student=student,
            email=email,
            permanent_address='Perm address',
            current_address='Curr address',
            mobile='9999999999',
            father_name='Father',
            mother_name='Mother',
            guardian_name='Guardian',
            parent_contact='8888888888',
        )
        StudentAdmissionDetails.objects.create(
            student=student,
            enrollment_number=enrollment_number,
            roll_number=roll_number,
            start_class_date=date(2026, 4, 1),
            academic_year='2026-2027',
        )
        StudentCourseAssignment.objects.create(
            student=student,
            class_name=class_name,
            branch=branch,
            academic_term=academic_term,
        )
        StudentSystemDetails.objects.create(
            student=student,
            student_personal_id=personal_id,
            library_card_number=f'LIB-{student.id}',
            hostel_details='Hostel A',
            verification_status='verified',
        )
        SubjectsAssigned.objects.bulk_create([
            SubjectsAssigned(student=student, subject=subject, unit=unit)
            for subject, unit in subjects
        ])
        return student

    def create_matching_published_snapshot(self, student):
        PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=student.id,
            name=student.name,
            student_personal_id=student.system_details.student_personal_id,
            student_data=build_student_snapshot(student),
            subjects_assigned=build_subjects_snapshot(student),
        )

    def create_changed_published_snapshot(self, student):
        student_data = build_student_snapshot(student)
        student_data['contact_details']['email'] = 'old@example.com'
        PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=student.id,
            name=student.name,
            student_personal_id=student.system_details.student_personal_id,
            student_data=student_data,
            subjects_assigned=build_subjects_snapshot(student),
        )

    def create_subject_changed_snapshot(self, student):
        PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=student.id,
            name=student.name,
            student_personal_id=student.system_details.student_personal_id,
            student_data=build_student_snapshot(student),
            subjects_assigned=[],
        )

    def test_students_bulk_returns_scope_rows_with_publish_status_counts(self):
        response = self.client.get(
            f"{self.url}&class_name=B.A&branch=History&academic_term=1st Semester",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)
        self.assertEqual(response.data['publish_counts'], {'new': 1, 'update': 2, 'exist': 1})
        students_by_id = {student['id']: student for student in response.data['students']}
        self.assertEqual(students_by_id[self.new_student.id]['publish_status'], 'new')
        self.assertEqual(students_by_id[self.exist_student.id]['publish_status'], 'exist')
        self.assertEqual(students_by_id[self.changed_student.id]['publish_status'], 'update')
        self.assertEqual(students_by_id[self.subject_changed_student.id]['publish_status'], 'update')
        self.assertNotIn(self.other_scope_student.id, students_by_id)

    def test_students_bulk_marks_update_when_nested_student_data_changes(self):
        response = self.client.get(
            f"{self.url}&class_name=B.A&branch=History&academic_term=1st Semester",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        students_by_id = {student['id']: student for student in response.data['students']}
        self.assertEqual(students_by_id[self.changed_student.id]['publish_status'], 'update')

    def test_students_bulk_marks_update_when_subjects_change(self):
        response = self.client.get(
            f"{self.url}&class_name=B.A&branch=History&academic_term=1st Semester",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        students_by_id = {student['id']: student for student in response.data['students']}
        self.assertEqual(students_by_id[self.subject_changed_student.id]['publish_status'], 'update')

    def test_students_bulk_uses_small_fixed_query_count(self):
        for index in range(30):
            student = self.create_student(
                name=f'Bulk Perf Student {index + 1}',
                email=f'perf{index + 1}@example.com',
                roll_number=f'ROLL-PERF-{index + 1}',
                enrollment_number=f'ENR-PERF-{index + 1}',
                class_name='B.A',
                branch='History',
                academic_term='1st Semester',
                personal_id=f'PERF-BULK-{index + 1:04d}',
                subjects=[('History', '1')],
            )
            self.create_matching_published_snapshot(student)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f"{self.url}&class_name=B.A&branch=History&academic_term=1st Semester",
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 34)
        self.assertLessEqual(len(queries), 6)


class SyllabusStudentsBulkTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Syllabus Institute',
            admin_key='s' * 32,
            event_status='active',
        )
        self.other_institute = Institute.objects.create(
            name='Other Institute',
            admin_key='o' * 32,
            event_status='active',
        )
        self.url = f"{reverse('syllabus-students')}?institute={self.institute.id}"
        self.students = []
        for index in range(3):
            student = Student.objects.create(
                institute=self.institute,
                name=f'History Student {index + 1}',
                gender='Female',
            )
            StudentContactDetails.objects.create(
                student=student,
                email=f'history{index + 1}@example.com',
            )
            StudentAdmissionDetails.objects.create(
                student=student,
                roll_number=f'HIST-{index + 1}',
                enrollment_number=f'ENR-HIST-{index + 1}',
            )
            StudentCourseAssignment.objects.create(
                student=student,
                class_name='B.A',
                branch='History',
                academic_term='1st Semester',
            )
            StudentSystemDetails.objects.create(
                student=student,
                student_personal_id=f'HIST-PERSONAL-{index + 1}',
            )
            self.students.append(student)

        other_class_student = Student.objects.create(
            institute=self.institute,
            name='Physics Search Match',
            gender='Male',
        )
        StudentAdmissionDetails.objects.create(
            student=other_class_student,
            roll_number='HIST-2',
        )
        StudentCourseAssignment.objects.create(
            student=other_class_student,
            class_name='B.Sc',
            branch='Physics',
            academic_term='1st Semester',
        )

        self.other_institute_student = Student.objects.create(
            institute=self.other_institute,
            name='History Student Other Institute',
            gender='Female',
        )
        StudentCourseAssignment.objects.create(
            student=self.other_institute_student,
            class_name='B.A',
            branch='History',
            academic_term='1st Semester',
        )

        SubjectsAssigned.objects.create(
            student=self.students[0],
            subject='Math',
            unit='1',
        )
        SubjectsAssigned.objects.create(
            student=self.students[0],
            subject='History',
            unit='2',
        )

    def test_bulk_syllabus_students_include_details_and_assigned_subjects(self):
        response = self.client.get(
            f"{self.url}&class_name=B.A&branch=History&academic_term=1st Semester&page=1&page_size=2",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['context_count'], 3)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['page_size'], 2)
        self.assertEqual(len(response.data['students']), 2)
        first_student = response.data['students'][0]
        self.assertEqual(first_student['id'], self.students[0].id)
        self.assertEqual(first_student['admission_details']['roll_number'], 'HIST-1')
        self.assertEqual(first_student['course_assignment']['branch'], 'History')
        self.assertEqual(len(first_student['subjects_assigned']), 2)
        self.assertEqual(first_student['subjects_assigned'][0]['subject'], 'Math')
        response_ids = [student['id'] for student in response.data['students']]
        self.assertNotIn(self.other_institute_student.id, response_ids)

    def test_bulk_syllabus_students_returns_requested_page_only(self):
        response = self.client.get(
            f"{self.url}&class_name=B.A&branch=History&academic_term=1st Semester&page=2&page_size=2",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['context_count'], 3)
        self.assertEqual(response.data['page'], 2)
        self.assertEqual(response.data['page_size'], 2)
        self.assertEqual(len(response.data['students']), 1)
        self.assertEqual(response.data['students'][0]['id'], self.students[2].id)

    def test_bulk_syllabus_students_search_count_keeps_context_count(self):
        response = self.client.get(
            f"{self.url}&class_name=B.A&branch=History&academic_term=1st Semester&search=HIST-2",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['context_count'], 3)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['students'][0]['id'], self.students[1].id)

    def test_bulk_syllabus_students_requires_class_name(self):
        response = self.client.get(
            self.url,
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'class_name query param is required.')

    def test_bulk_syllabus_students_uses_small_fixed_query_count(self):
        for index in range(30):
            student = Student.objects.create(
                institute=self.institute,
                name=f'Bulk Student {index + 1}',
                gender='Female',
            )
            StudentCourseAssignment.objects.create(
                student=student,
                class_name='B.A',
                branch='History',
                academic_term='1st Semester',
            )
            SubjectsAssigned.objects.create(
                student=student,
                subject='Math',
                unit='1',
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f"{self.url}&class_name=B.A&branch=History&academic_term=1st Semester",
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 33)
        self.assertEqual(len(response.data['students']), 25)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['page_size'], 25)
        self.assertLessEqual(len(queries), 7)


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

    def test_assign_multiple_subjects_by_class_branch_and_academic_term(self):
        SubjectsAssigned.objects.create(
            student=self.matching_students[0],
            subject='Math',
            unit='1',
        )

        response = self.client.post(
            self.url,
            {
                'subjects': [
                    {'subject': 'Math', 'unit': '1'},
                    {'subject': 'Physics', 'unit': '2'},
                ],
                'class_name': 'B.A',
                'branch': 'History',
                'academic_term': '1st Semester',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['matched_students'], 40)
        self.assertEqual(response.data['assigned_subject_count'], 2)
        self.assertEqual(response.data['created_count'], 79)
        self.assertEqual(response.data['already_assigned_count'], 1)
        self.assertEqual(
            SubjectsAssigned.objects.filter(subject='Math', student__in=self.matching_students).count(),
            40,
        )
        self.assertEqual(
            SubjectsAssigned.objects.filter(subject='Physics', student__in=self.matching_students).count(),
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
        self.assertLessEqual(len(queries), 7)

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
        self.assertLessEqual(len(queries), 7)

    def test_multi_subject_hierarchy_assignment_uses_small_fixed_query_count(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                self.url,
                {
                    'subjects': [
                        {'subject': 'Chemistry', 'unit': '3'},
                        {'subject': 'Botany', 'unit': '4'},
                    ],
                    'class_name': 'B.A',
                    'branch': 'History',
                    'academic_term': '1st Semester',
                },
                format='json',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_count'], 80)
        self.assertEqual(response.data['assigned_subject_count'], 2)
        self.assertEqual(ActivityEvent.objects.count(), 1)
        self.assertLessEqual(len(queries), 7)
