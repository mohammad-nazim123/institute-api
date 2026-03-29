from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from iinstitutes_list.models import Institute
from professors.models import Professor, professorAdminEmployement
from students.models import Student, StudentSystemDetails

from .models import ExamData, ObtainedMarks


class ObtainedMarksApiTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Exam Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.other_institute = Institute.objects.create(
            name='Other Institute',
            admin_key='b' * 32,
            event_status='active',
        )
        self.admin_headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Professor One',
            email='professor@example.com',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='2' * 15,
            employee_id='EMP001',
        )

        self.student = Student.objects.create(
            institute=self.institute,
            name='Student One',
        )
        self.other_student = Student.objects.create(
            institute=self.institute,
            name='Student Two',
        )
        self.outside_student = Student.objects.create(
            institute=self.other_institute,
            name='Outside Student',
        )
        StudentSystemDetails.objects.create(
            student=self.student,
            student_personal_id='1' * 15,
        )

        self.exam = ExamData.objects.create(
            institute=self.institute,
            class_name='BSc',
            branch='CS',
            academic_term='Semester 1',
            subject='Physics',
            exam_type='Midterm',
            date='2026-03-20',
            duration=90,
            total_marks=100,
        )

    def test_admin_can_crud_obtained_marks(self):
        create_response = self.client.post(
            f"{reverse('obtained-marks-list-create')}?institute={self.institute.id}",
            {
                'exam_data': self.exam.id,
                'student': self.student.id,
                'obtained_marks': 88,
            },
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['obtained_marks'], 88)
        marks_id = create_response.data['id']

        list_response = self.client.get(
            f"{reverse('obtained-marks-list-create')}?institute={self.institute.id}"
            '&class_name=BSc&branch=CS&academic_term=Semester 1',
            **self.admin_headers,
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['student_name'], 'Student One')

        patch_response = self.client.patch(
            f"{reverse('obtained-marks-detail', kwargs={'pk': marks_id})}?institute={self.institute.id}",
            {'obtained_marks': 91},
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['obtained_marks'], 91)

        delete_response = self.client.delete(
            f"{reverse('obtained-marks-detail', kwargs={'pk': marks_id})}?institute={self.institute.id}",
            **self.admin_headers,
        )

        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(ObtainedMarks.objects.filter(pk=marks_id).exists())

    def test_create_rejects_obtained_marks_above_total_marks(self):
        response = self.client.post(
            f"{reverse('obtained-marks-list-create')}?institute={self.institute.id}",
            {
                'exam_data': self.exam.id,
                'student': self.student.id,
                'obtained_marks': 101,
            },
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['obtained_marks'][0],
            'Obtained marks cannot be greater than total marks (100).',
        )

    def test_patch_rejects_obtained_marks_above_total_marks(self):
        marks = ObtainedMarks.objects.create(
            exam_data=self.exam,
            student=self.student,
            obtained_marks=70,
        )

        response = self.client.patch(
            f"{reverse('obtained-marks-detail', kwargs={'pk': marks.id})}?institute={self.institute.id}",
            {'obtained_marks': 120},
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['obtained_marks'][0],
            'Obtained marks cannot be greater than total marks (100).',
        )

    def test_create_rejects_student_from_other_institute(self):
        response = self.client.post(
            f"{reverse('obtained-marks-list-create')}?institute={self.institute.id}",
            {
                'exam_data': self.exam.id,
                'student': self.outside_student.id,
                'obtained_marks': 85,
            },
            format='json',
            **self.admin_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['student'][0],
            'Student must belong to the same institute as the exam.',
        )

    def test_student_key_only_returns_their_own_marks_and_cannot_write(self):
        own_marks = ObtainedMarks.objects.create(
            exam_data=self.exam,
            student=self.student,
            obtained_marks=91,
        )
        ObtainedMarks.objects.create(
            exam_data=self.exam,
            student=self.other_student,
            obtained_marks=76,
        )

        list_response = self.client.get(
            f"{reverse('obtained-marks-list-create')}?institute={self.institute.id}",
            HTTP_X_PERSONAL_KEY='1' * 15,
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['id'], own_marks.id)

        create_response = self.client.post(
            f"{reverse('obtained-marks-list-create')}?institute={self.institute.id}",
            {
                'exam_data': self.exam.id,
                'student': self.student.id,
                'obtained_marks': 93,
            },
            format='json',
            HTTP_X_PERSONAL_KEY='1' * 15,
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_professor_personal_key_can_create_marks(self):
        response = self.client.post(
            f"{reverse('obtained-marks-list-create')}?institute={self.institute.id}",
            {
                'exam_data': self.exam.id,
                'student': self.student.id,
                'obtained_marks': 84,
            },
            format='json',
            HTTP_X_PERSONAL_KEY='2' * 15,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['obtained_marks'], 84)
