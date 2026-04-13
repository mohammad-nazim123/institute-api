from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from students.models import (
    Student,
    StudentAdmissionDetails,
    StudentContactDetails,
    StudentCourseAssignment,
    StudentEducationDetails,
    StudentFeeDetails,
    StudentSystemDetails,
    SubjectsAssigned,
)

from .models import PublishedStudent


class PublishedStudentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Alpha Institute',
            admin_key='a' * 32,
        )
        self.student = self.create_student(
            name='Alice',
            email='alice@example.com',
            personal_id='STUDENT-0000001',
            academic_term='1st semester',
        )

    def create_student(self, name, email, personal_id, academic_term):
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
        StudentEducationDetails.objects.create(
            student=student,
            qualification='12th',
            passing_year=2024,
            institute_name='ABC School',
            marks_obtained='92',
        )
        StudentAdmissionDetails.objects.create(
            student=student,
            enrollment_number='ENR-1',
            roll_number='ROLL-1',
            start_class_date='2026-04-01',
            academic_year='2026-2027',
        )
        StudentCourseAssignment.objects.create(
            student=student,
            class_name='B.Tech',
            branch='CS',
            academic_term=academic_term,
        )
        StudentFeeDetails.objects.create(
            student=student,
            total_fee_amount=100000,
            paid_amount=40000,
            pending_amount=60000,
        )
        StudentSystemDetails.objects.create(
            student=student,
            student_personal_id=personal_id,
            library_card_number='LIB-1',
            hostel_details='Hostel A',
            verification_status='verified',
        )
        SubjectsAssigned.objects.bulk_create([
            SubjectsAssigned(student=student, subject='Math', unit='1'),
            SubjectsAssigned(student=student, subject='Physics', unit='2'),
        ])
        return student

    def publish_all(self):
        return self.client.post(
            f'/published_students/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

    def test_publish_transfers_student_and_subjects(self):
        response = self.publish_all()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(len(response.data['published_students']), 1)
        published = response.data['published_students'][0]
        self.assertEqual(published['student_id'], self.student.id)
        self.assertEqual(published['student_data']['course_assignment']['branch'], 'CS')
        self.assertEqual(
            published['student_data']['admission_details']['start_class_date'],
            '2026-04-01',
        )
        self.assertEqual(
            published['student_data']['admission_details']['academic_year'],
            '2026-2027',
        )
        self.assertEqual(len(published['subjects_assigned']), 2)
        self.assertNotIn('published_key', published)

    def test_publish_creates_missing_student_records(self):
        self.create_student(
            name='Bob',
            email='bob@example.com',
            personal_id='STUDENT-0000002',
            academic_term='2nd semester',
        )

        response = self.publish_all()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 2)
        self.assertEqual(response.data['updated_count'], 0)
        self.assertEqual(response.data['already_exists_count'], 0)
        self.assertEqual(PublishedStudent.objects.filter(institute=self.institute).count(), 2)

    def test_publish_updates_existing_student_when_any_data_changes(self):
        other_student = self.create_student(
            name='Bob',
            email='bob@example.com',
            personal_id='STUDENT-0000002',
            academic_term='2nd semester',
        )
        PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=other_student.id,
            name='Old Bob',
            student_personal_id='STUDENT-0000002',
            student_data={'id': other_student.id, 'name': 'Old Bob'},
            subjects_assigned=[],
        )

        response = self.publish_all()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(response.data['updated_count'], 1)
        self.assertEqual(response.data['already_exists_count'], 0)

        snapshot = PublishedStudent.objects.get(
            institute=self.institute,
            source_student_id=other_student.id,
        )
        self.assertEqual(snapshot.name, 'Bob')
        self.assertEqual(
            snapshot.student_data['course_assignment']['academic_term'],
            '2nd semester',
        )

    def test_publish_returns_already_exists_message_when_no_student_data_changes(self):
        first_response = self.publish_all()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.data['created_count'], 1)

        second_response = self.publish_all()

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data['created_count'], 0)
        self.assertEqual(second_response.data['updated_count'], 0)
        self.assertEqual(second_response.data['already_exists_count'], 1)
        self.assertEqual(second_response.data['message'], 'The data already exist.')
        self.assertEqual(second_response.data['detail'], 'The data already exist.')
        self.assertEqual(second_response.data['already_exists_student_ids'], [self.student.id])

    def test_publish_uses_six_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.publish_all()

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 6)

    def test_fetch_by_student_id_requires_15_char_header_and_returns_institute_dict(self):
        self.publish_all()
        published = PublishedStudent.objects.get(
            institute=self.institute,
            source_student_id=self.student.id,
        )

        response = self.client.get(
            f'/published_students/{self.student.id}/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY=published.student_personal_id,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['published_students'][0]['student_id'], self.student.id)
        self.assertEqual(
            response.data['published_students'][0]['subjects_assigned'][0]['subject'],
            'Math',
        )

    def test_lookup_id_by_personal_key_returns_student_id(self):
        self.publish_all()

        response = self.client.get(
            f'/published_students/lookup-id/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='STUDENT-0000001',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['student_id'], self.student.id)

    def test_fetch_rejects_non_15_char_header(self):
        self.publish_all()

        response = self.client.get(
            f'/published_students/{self.student.id}/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='SHORTKEY',
        )

        self.assertEqual(response.status_code, 403)

    def test_fetch_uses_two_queries_or_less(self):
        self.publish_all()
        published = PublishedStudent.objects.get(
            institute=self.institute,
            source_student_id=self.student.id,
        )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/published_students/{self.student.id}/?institute={self.institute.id}',
                HTTP_X_PERSONAL_KEY=published.student_personal_id,
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 2)

    def test_admin_patch_updates_snapshot(self):
        self.publish_all()

        response = self.client.patch(
            f'/published_students/{self.student.id}/?institute={self.institute.id}',
            data={
                'name': 'Published Alice',
                'subjects_assigned': [{'subject': 'Chemistry', 'unit': '3'}],
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['published_students'][0]['name'], 'Published Alice')
        self.assertEqual(
            response.data['published_students'][0]['subjects_assigned'][0]['subject'],
            'Chemistry',
        )
