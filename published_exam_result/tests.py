from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from published_student.models import PublishedStudent
from set_exam_data.models import ExamData, ObtainedMarks
from students.models import Student, StudentSystemDetails
from subordinate_access.models import SubordinateAccess

from .models import PublishedExamResult


class PublishedExamResultApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Result Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.other_institute = Institute.objects.create(
            name='Other Institute',
            admin_key='b' * 32,
            event_status='active',
        )
        self.admin_headers = {'HTTP_X_ADMIN_KEY': self.institute.admin_key}
        self.subordinate_31 = SubordinateAccess.objects.create(
            institute=self.institute,
            post='Manager',
            name='Manager One',
            access_control='admin access',
            access_code='M' * 31,
            is_active=True,
        )
        self.subordinate_30 = SubordinateAccess.objects.create(
            institute=self.institute,
            post='Student Desk',
            name='Desk Two',
            access_control='student access',
            access_code='S' * 30,
            is_active=True,
        )

        self.student_one = Student.objects.create(
            institute=self.institute,
            name='Student One',
        )
        self.student_two = Student.objects.create(
            institute=self.institute,
            name='Student Two',
        )
        self.student_three = Student.objects.create(
            institute=self.institute,
            name='Student Three',
        )
        self.other_student = Student.objects.create(
            institute=self.other_institute,
            name='Outside Student',
        )
        StudentSystemDetails.objects.create(
            student=self.student_one,
            student_personal_id='STUDENT-0000001',
        )
        StudentSystemDetails.objects.create(
            student=self.student_two,
            student_personal_id='STUDENT-0000002',
        )
        StudentSystemDetails.objects.create(
            student=self.student_three,
            student_personal_id='STUDENT-0000003',
        )

        self.published_student_one = PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=self.student_one.id,
            name=self.student_one.name,
            student_personal_id='STUDENT-0000001',
            student_data={},
            subjects_assigned=[],
        )
        self.published_student_two = PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=self.student_two.id,
            name=self.student_two.name,
            student_personal_id='STUDENT-0000002',
            student_data={},
            subjects_assigned=[],
        )
        self.published_student_three = PublishedStudent.objects.create(
            institute=self.institute,
            source_student_id=self.student_three.id,
            name=self.student_three.name,
            student_personal_id='STUDENT-0000003',
            student_data={},
            subjects_assigned=[],
        )
        self.other_published_student = PublishedStudent.objects.create(
            institute=self.other_institute,
            source_student_id=self.other_student.id,
            name=self.other_student.name,
            student_personal_id='OUTSIDE-STUDENT',
            student_data={},
            subjects_assigned=[],
        )

        self.exam_one = ExamData.objects.create(
            institute=self.institute,
            class_name='B.A',
            branch='History',
            academic_term='2nd Semester',
            subject='History of India',
            exam_type='Final',
            date=date(2026, 3, 20),
            duration=180,
            total_marks=100,
        )
        self.exam_two = ExamData.objects.create(
            institute=self.institute,
            class_name='B.A',
            branch='History',
            academic_term='2nd Semester',
            subject='Political Theory',
            exam_type='Internal',
            date=date(2026, 3, 25),
            duration=90,
            total_marks=40,
        )
        self.outside_exam = ExamData.objects.create(
            institute=self.other_institute,
            class_name='B.A',
            branch='History',
            academic_term='2nd Semester',
            subject='Outside Exam',
            exam_type='Final',
            date=date(2026, 3, 30),
            duration=180,
            total_marks=100,
        )

        ObtainedMarks.objects.create(
            exam_data=self.exam_one,
            student=self.student_one,
            obtained_marks=88,
        )
        ObtainedMarks.objects.create(
            exam_data=self.exam_two,
            student=self.student_one,
            obtained_marks=29,
        )
        ObtainedMarks.objects.create(
            exam_data=self.exam_one,
            student=self.student_two,
            obtained_marks=74,
        )
        ObtainedMarks.objects.create(
            exam_data=self.outside_exam,
            student=self.other_student,
            obtained_marks=90,
        )

    def _list_url(self):
        return f'/institutes/published_exam_results/?institute={self.institute.id}'

    def _detail_url(self, student_id):
        return f'/institutes/published_exam_results/{student_id}/?institute={self.institute.id}'

    def test_post_syncs_all_published_student_exam_results_from_obtained_marks(self):
        response = self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 2)
        self.assertEqual(len(response.data['published_exam_results']), 2)
        self.assertEqual(PublishedExamResult.objects.filter(institute=self.institute).count(), 2)
        self.assertFalse(
            any(item['student_id'] == self.student_three.id for item in response.data['published_exam_results'])
        )

        first_result = response.data['published_exam_results'][0]
        self.assertIn(first_result['student_id'], {self.student_one.id, self.student_two.id})
        student_one_payload = next(
            item for item in response.data['published_exam_results']
            if item['student_id'] == self.student_one.id
        )
        self.assertEqual(len(student_one_payload['exam_results']), 2)
        self.assertEqual(student_one_payload['exam_results'][0]['status'], 'Pass')
        self.assertEqual(student_one_payload['exam_results'][1]['status'], 'Pass')

    def test_post_reports_already_exists_when_bulk_publish_has_no_changes(self):
        first_response = self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )
        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data['created_count'], 0)
        self.assertEqual(second_response.data['updated_count'], 0)
        self.assertEqual(second_response.data['already_exists_count'], 2)
        self.assertEqual(second_response.data['deleted_count'], 0)
        self.assertEqual(second_response.data['detail'], 'The data already exist.')

    def test_post_deletes_existing_published_result_when_student_has_no_obtained_marks(self):
        first_response = self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )
        self.assertEqual(first_response.status_code, 200)

        ObtainedMarks.objects.filter(
            exam_data=self.exam_one,
            student=self.student_two,
        ).delete()

        second_response = self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data['created_count'], 0)
        self.assertEqual(second_response.data['updated_count'], 0)
        self.assertEqual(second_response.data['already_exists_count'], 1)
        self.assertEqual(second_response.data['deleted_count'], 1)
        self.assertEqual(len(second_response.data['published_exam_results']), 1)
        self.assertFalse(
            PublishedExamResult.objects.filter(
                institute=self.institute,
                source_student_id=self.student_two.id,
            ).exists()
        )

    def test_post_single_student_without_marks_returns_info_message(self):
        response = self.client.post(
            self._list_url(),
            data={'student_id': self.student_three.id},
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 0)
        self.assertEqual(response.data['updated_count'], 0)
        self.assertEqual(response.data['already_exists_count'], 0)
        self.assertEqual(response.data['deleted_count'], 0)
        self.assertEqual(response.data['detail'], 'No obtained marks found to publish.')
        self.assertEqual(response.data['published_exam_results'], [])

    def test_get_list_is_scoped_to_institute(self):
        PublishedExamResult.objects.create(
            institute=self.other_institute,
            published_student=self.other_published_student,
            source_student_id=self.other_student.id,
            name='Wrong Institute Result',
            student_personal_id='WRONG',
            exam_results=[],
            published_at='2026-03-31T00:00:00Z',
            updated_at='2026-03-31T00:00:00Z',
        )

        response = self.client.get(
            self._list_url(),
            **self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['published_exam_results'], [])

    def test_patch_refreshes_single_result_with_31_char_subordinate_key(self):
        self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )
        result = PublishedExamResult.objects.get(
            institute=self.institute,
            source_student_id=self.student_one.id,
        )
        mark = ObtainedMarks.objects.get(
            exam_data=self.exam_one,
            student=self.student_one,
        )
        mark.obtained_marks = 95
        mark.save(update_fields=['obtained_marks'])

        response = self.client.patch(
            self._detail_url(self.student_one.id),
            data={},
            format='json',
            HTTP_X_ADMIN_KEY='M' * 31,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'Published exam result updated successfully.')
        result.refresh_from_db()
        updated_entry = next(
            item for item in result.exam_results if item['exam_data_id'] == self.exam_one.id
        )
        self.assertEqual(updated_entry['obtained_marks'], 95)

    def test_student_personal_key_can_get_own_published_exam_result(self):
        self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        response = self.client.get(
            self._detail_url(self.student_one.id),
            HTTP_X_PERSONAL_KEY='STUDENT-0000001',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['student_id'], self.student_one.id)
        self.assertEqual(len(response.data['exam_results']), 2)

    def test_student_personal_key_cannot_get_another_students_published_exam_result(self):
        self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        response = self.client.get(
            self._detail_url(self.student_two.id),
            HTTP_X_PERSONAL_KEY='STUDENT-0000001',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data['detail'],
            'Students can only view their own published exam result.',
        )

    def test_delete_works_with_30_char_subordinate_key(self):
        self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        response = self.client.delete(
            self._detail_url(self.student_two.id),
            HTTP_X_ADMIN_KEY='S' * 30,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], 'Published exam result deleted successfully.')
        self.assertFalse(
            PublishedExamResult.objects.filter(
                institute=self.institute,
                source_student_id=self.student_two.id,
            ).exists()
        )

    def test_rejects_keys_outside_30_31_32_characters(self):
        response = self.client.get(
            self._list_url(),
            HTTP_X_ADMIN_KEY='Z' * 29,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data['detail'],
            'Provide X-Admin-Key or admin_key with exactly 30, 31, or 32 characters.',
        )
