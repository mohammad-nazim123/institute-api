from datetime import date
from urllib.parse import urlencode

from django.test import TestCase
from rest_framework.test import APIClient

from iinstitutes_list.academic_terms import rename_institute_academic_term
from iinstitutes_list.models import Institute
from published_student.models import PublishedStudent
from set_exam_data.models import ExamData, ObtainedMarks
from students.models import Student, StudentSystemDetails
from subordinate_access.models import SubordinateAccess

from .models import PublishedExamData, PublishedObtainedMarks


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
        self.other_admin_headers = {'HTTP_X_ADMIN_KEY': self.other_institute.admin_key}
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

        self.exam_final_history = ExamData.objects.create(
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
        self.exam_final_world = ExamData.objects.create(
            institute=self.institute,
            class_name='B.A',
            branch='History',
            academic_term='2nd Semester',
            subject='World History',
            exam_type='Final',
            date=date(2026, 3, 22),
            duration=120,
            total_marks=80,
        )
        self.exam_internal = ExamData.objects.create(
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

        self.student_one_final_history_mark = ObtainedMarks.objects.create(
            exam_data=self.exam_final_history,
            student=self.student_one,
            obtained_marks=88,
        )
        self.student_one_final_world_mark = ObtainedMarks.objects.create(
            exam_data=self.exam_final_world,
            student=self.student_one,
            obtained_marks=61,
        )
        self.student_one_internal_mark = ObtainedMarks.objects.create(
            exam_data=self.exam_internal,
            student=self.student_one,
            obtained_marks=29,
        )
        self.student_two_final_history_mark = ObtainedMarks.objects.create(
            exam_data=self.exam_final_history,
            student=self.student_two,
            obtained_marks=74,
        )
        self.other_student_mark = ObtainedMarks.objects.create(
            exam_data=self.outside_exam,
            student=self.other_student,
            obtained_marks=90,
        )

    def _query_string(self, institute_id, **query):
        params = {'institute': institute_id}
        for key, value in query.items():
            if value is not None and value != '':
                params[key] = value
        return urlencode(params)

    def _list_url(self, **query):
        return f'/institutes/published_exam_results/?{self._query_string(self.institute.id, **query)}'

    def _other_list_url(self, **query):
        return f'/institutes/published_exam_results/?{self._query_string(self.other_institute.id, **query)}'

    def _detail_url(self, student_id, **query):
        return f'/institutes/published_exam_results/{student_id}/?{self._query_string(self.institute.id, **query)}'

    def test_post_bulk_syncs_flat_rows_into_relational_models(self):
        response = self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 2)
        self.assertEqual(response.data['updated_count'], 0)
        self.assertEqual(response.data['already_exists_count'], 0)
        self.assertEqual(response.data['deleted_count'], 0)
        self.assertEqual(PublishedExamData.objects.filter(institute=self.institute).count(), 3)
        self.assertEqual(
            PublishedObtainedMarks.objects.filter(published_student__institute=self.institute).count(),
            4,
        )

        rows = response.data['published_exam_results']
        self.assertEqual(len(rows), 4)
        self.assertTrue(all('published_exam_data_id' in row for row in rows))
        self.assertTrue(all('source_obtained_marks_id' in row for row in rows))
        self.assertTrue(all('exam_results' not in row for row in rows))

        student_one_rows = [row for row in rows if row['student_id'] == self.student_one.id]
        self.assertEqual(len(student_one_rows), 3)
        self.assertEqual(
            {row['subject'] for row in student_one_rows},
            {'History of India', 'World History', 'Political Theory'},
        )

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

    def test_post_single_student_scope_updates_rows_and_removes_stale_scope_entries(self):
        first_response = self.client.post(
            self._list_url(
                class_name='B.A',
                branch='History',
                academic_term='2nd Semester',
                exam_type='Final',
            ),
            data={'student_id': self.student_one.id},
            format='json',
            **self.admin_headers,
        )
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.data['created_count'], 1)
        self.assertEqual(len(first_response.data['published_exam_results']), 2)

        self.exam_final_history.duration = 200
        self.exam_final_history.save(update_fields=['duration'])
        self.student_one_final_history_mark.obtained_marks = 95
        self.student_one_final_history_mark.save(update_fields=['obtained_marks'])
        self.student_one_final_world_mark.delete()

        second_response = self.client.post(
            self._list_url(
                class_name='B.A',
                branch='History',
                academic_term='2nd Semester',
                exam_type='Final',
            ),
            data={'student_id': self.student_one.id},
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data['created_count'], 0)
        self.assertEqual(second_response.data['updated_count'], 1)
        self.assertEqual(second_response.data['already_exists_count'], 0)
        self.assertEqual(second_response.data['deleted_count'], 0)
        rows = second_response.data['published_exam_results']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['subject'], 'History of India')
        self.assertEqual(rows[0]['obtained_marks'], 95)
        self.assertEqual(rows[0]['duration'], 200)
        self.assertFalse(
            PublishedObtainedMarks.objects.filter(
                source_obtained_marks_id=self.student_one_final_world_mark.id
            ).exists()
        )

    def test_get_list_filters_by_scope_and_stays_scoped_to_institute(self):
        self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )
        self.client.post(
            self._other_list_url(),
            format='json',
            **self.other_admin_headers,
        )

        response = self.client.get(
            self._list_url(
                class_name='B.A',
                branch='History',
                academic_term='2nd Semester',
                exam_type='Final',
            ),
            **self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        rows = response.data['published_exam_results']
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row['exam_type'] == 'Final' for row in rows))
        self.assertFalse(any(row['student_id'] == self.other_student.id for row in rows))

    def test_patch_refreshes_single_result_with_31_char_subordinate_key(self):
        self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        self.student_one_internal_mark.obtained_marks = 35
        self.student_one_internal_mark.save(update_fields=['obtained_marks'])

        response = self.client.patch(
            self._detail_url(
                self.student_one.id,
                class_name='B.A',
                branch='History',
                academic_term='2nd Semester',
                exam_type='Internal',
            ),
            data={},
            format='json',
            HTTP_X_ADMIN_KEY='M' * 31,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'Published exam result updated successfully.')
        rows = response.data['published_exam_results']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['obtained_marks'], 35)

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
        rows = response.data['published_exam_results']
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row['student_id'] == self.student_one.id for row in rows))

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

    def test_delete_works_with_30_char_subordinate_key_for_scoped_rows(self):
        self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        response = self.client.delete(
            self._detail_url(
                self.student_one.id,
                class_name='B.A',
                branch='History',
                academic_term='2nd Semester',
                exam_type='Internal',
            ),
            HTTP_X_ADMIN_KEY='S' * 30,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], 'Published exam result deleted successfully.')
        self.assertFalse(
            PublishedObtainedMarks.objects.filter(
                source_obtained_marks_id=self.student_one_internal_mark.id,
            ).exists()
        )
        self.assertTrue(
            PublishedObtainedMarks.objects.filter(
                source_obtained_marks_id=self.student_one_final_history_mark.id,
            ).exists()
        )

    def test_rename_institute_academic_term_updates_published_exam_data(self):
        self.client.post(
            self._list_url(),
            format='json',
            **self.admin_headers,
        )

        summary = rename_institute_academic_term(
            self.institute,
            '2nd Semester',
            'Semester 2',
        )

        self.assertGreaterEqual(summary['published_exam_results'], 1)
        self.assertFalse(
            PublishedExamData.objects.filter(
                institute=self.institute,
                academic_term='2nd Semester',
            ).exists()
        )
        self.assertTrue(
            PublishedExamData.objects.filter(
                institute=self.institute,
                academic_term='Semester 2',
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
