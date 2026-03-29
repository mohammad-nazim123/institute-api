from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from professors.models import Professor, ProfessorExperience, professorAdminEmployement
from published_professors.models import PublishedProfessor

from .models import InstituteTotalLeave, ProfessorLeave


class ProfessorLeavesBaseTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Alpha Institute',
            admin_key='a' * 32,
        )
        self.other_institute = Institute.objects.create(
            name='Beta Institute',
            admin_key='b' * 32,
        )

        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Bob',
            email='bob@example.com',
        )
        ProfessorExperience.objects.create(
            professor=self.professor,
            department='CSE',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='PROF00000000001',
            employee_id='EMP-1',
        )
        self.published_professor = PublishedProfessor.objects.create(
            institute=self.institute,
            source_professor_id=self.professor.id,
            name='Dr Bob',
            email='bob@example.com',
            professor_personal_id='PROF00000000001',
            professor_data={
                'id': self.professor.id,
                'name': 'Dr Bob',
                'email': 'bob@example.com',
                'experience': {
                    'department': 'CSE',
                },
            },
        )
        self.second_professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Alice',
            email='alice@example.com',
        )
        ProfessorExperience.objects.create(
            professor=self.second_professor,
            department='AI',
        )
        professorAdminEmployement.objects.create(
            professor=self.second_professor,
            personal_id='PROF00000000003',
            employee_id='EMP-3',
        )
        self.second_published_professor = PublishedProfessor.objects.create(
            institute=self.institute,
            source_professor_id=self.second_professor.id,
            name='Dr Alice',
            email='alice@example.com',
            professor_personal_id='PROF00000000003',
            professor_data={
                'id': self.second_professor.id,
                'name': 'Dr Alice',
                'email': 'alice@example.com',
                'experience': {
                    'department': 'AI',
                },
            },
        )

        self.other_professor = Professor.objects.create(
            institute=self.other_institute,
            name='Dr Eve',
            email='eve@example.com',
        )
        ProfessorExperience.objects.create(
            professor=self.other_professor,
            department='ECE',
        )
        professorAdminEmployement.objects.create(
            professor=self.other_professor,
            personal_id='PROF00000000002',
            employee_id='EMP-2',
        )
        self.other_published_professor = PublishedProfessor.objects.create(
            institute=self.other_institute,
            source_professor_id=self.other_professor.id,
            name='Dr Eve',
            email='eve@example.com',
            professor_personal_id='PROF00000000002',
            professor_data={
                'id': self.other_professor.id,
                'name': 'Dr Eve',
                'email': 'eve@example.com',
                'experience': {
                    'department': 'ECE',
                },
            },
        )


class ProfessorLeavesApiTests(ProfessorLeavesBaseTestCase):
    def test_create_leave_populates_professor_snapshot_fields(self):
        response = self.client.post(
            f'/professor_leaves/leaves/?institute={self.institute.id}',
            data={
                'published_professor': self.published_professor.id,
                'start_date': '2026-04-01',
                'end_date': '2026-04-03',
                'reason': 'Medical leave',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['professor_name'], 'Dr Bob')
        self.assertEqual(response.data['department'], 'CSE')
        self.assertEqual(response.data['email'], 'bob@example.com')
        self.assertEqual(response.data['reason'], 'Medical leave')
        self.assertEqual(response.data['leaves_status'], ProfessorLeave.LeaveStatus.PENDING)
        self.assertEqual(response.data['cancellation_reason'], '')
        self.assertEqual(response.data['total_days'], 3)
        self.assertIsNotNone(response.data['current_time'])
        self.assertNotIn('total_leaves', response.data)
        self.assertNotIn('remaining_leaves', response.data)

    def test_create_leave_rejects_published_professor_from_other_institute(self):
        response = self.client.post(
            f'/professor_leaves/leaves/?institute={self.institute.id}',
            data={
                'published_professor': self.other_published_professor.id,
                'start_date': '2026-04-01',
                'end_date': '2026-04-02',
                'reason': 'Conference',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('published_professor', response.data)

    def test_create_cancelled_leave_requires_cancellation_reason(self):
        response = self.client.post(
            f'/professor_leaves/leaves/?institute={self.institute.id}',
            data={
                'published_professor': self.published_professor.id,
                'start_date': '2026-04-04',
                'end_date': '2026-04-04',
                'reason': 'Trip cancelled',
                'leaves_status': ProfessorLeave.LeaveStatus.CANCELLED,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cancellation_reason', response.data)

    def test_create_cancelled_leave_accepts_cancellation_reason(self):
        response = self.client.post(
            f'/professor_leaves/leaves/?institute={self.institute.id}',
            data={
                'published_professor': self.published_professor.id,
                'start_date': '2026-04-04',
                'end_date': '2026-04-04',
                'reason': 'Trip cancelled',
                'leaves_status': ProfessorLeave.LeaveStatus.CANCELLED,
                'cancellation_reason': 'Event was postponed',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['leaves_status'], ProfessorLeave.LeaveStatus.CANCELLED)
        self.assertEqual(response.data['cancellation_reason'], 'Event was postponed')

    def test_leave_list_filters_by_published_professor(self):
        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 4, 5),
            end_date=date(2026, 4, 6),
            reason='Event',
        )

        response = self.client.get(
            f'/professor_leaves/leaves/?institute={self.institute.id}&published_professor={self.published_professor.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['professor_name'], 'Dr Bob')
        self.assertNotIn('total_leaves', response.data[0])
        self.assertNotIn('remaining_leaves', response.data[0])

    def test_retrieve_leave_returns_total_days(self):
        leave = ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 4, 7),
            end_date=date(2026, 4, 7),
            reason='Single day leave',
        )

        response = self.client.get(
            f'/professor_leaves/leaves/{leave.id}/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['professor_name'], 'Dr Bob')
        self.assertEqual(response.data['total_days'], 1)
        self.assertNotIn('total_leaves', response.data)
        self.assertNotIn('remaining_leaves', response.data)

    def test_update_leave_recomputes_total_days(self):
        leave = ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 4, 10),
            end_date=date(2026, 4, 11),
            reason='Personal',
        )

        response = self.client.patch(
            f'/professor_leaves/leaves/{leave.id}/?institute={self.institute.id}',
            data={
                'end_date': '2026-04-13',
                'reason': 'Extended personal leave',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['reason'], 'Extended personal leave')
        self.assertEqual(response.data['total_days'], 4)
        self.assertNotIn('total_leaves', response.data)
        self.assertNotIn('remaining_leaves', response.data)

    def test_updating_leave_to_non_cancelled_clears_cancellation_reason(self):
        leave = ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 4, 14),
            end_date=date(2026, 4, 14),
            reason='Cancelled class',
            leaves_status=ProfessorLeave.LeaveStatus.CANCELLED,
            cancellation_reason='Course was rescheduled',
        )

        response = self.client.patch(
            f'/professor_leaves/leaves/{leave.id}/?institute={self.institute.id}',
            data={
                'leaves_status': ProfessorLeave.LeaveStatus.ACCEPTED,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['leaves_status'], ProfessorLeave.LeaveStatus.ACCEPTED)
        self.assertEqual(response.data['cancellation_reason'], '')

    def test_delete_leave(self):
        leave = ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 4, 20),
            end_date=date(2026, 4, 20),
            reason='Emergency',
        )

        response = self.client.delete(
            f'/professor_leaves/leaves/{leave.id}/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProfessorLeave.objects.filter(id=leave.id).exists())

    def test_personal_key_can_create_own_leave(self):
        response = self.client.post(
            f'/professor_leaves/leaves/?institute={self.institute.id}',
            data={
                'start_date': '2026-04-25',
                'end_date': '2026-04-26',
                'reason': 'Personal leave',
            },
            format='json',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['professor_name'], 'Dr Bob')
        self.assertEqual(response.data['email'], 'bob@example.com')
        self.assertEqual(response.data['total_days'], 2)

    def test_personal_key_list_returns_only_own_leaves(self):
        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 27),
            reason='Own leave',
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.second_published_professor,
            professor_name='Dr Alice',
            department='AI',
            email='alice@example.com',
            start_date=date(2026, 4, 28),
            end_date=date(2026, 4, 28),
            reason='Other leave',
        )

        response = self.client.get(
            f'/professor_leaves/leaves/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['professor_name'], 'Dr Bob')

    def test_personal_key_cannot_create_leave_for_other_professor(self):
        response = self.client.post(
            f'/professor_leaves/leaves/?institute={self.institute.id}',
            data={
                'published_professor': self.second_published_professor.id,
                'start_date': '2026-04-29',
                'end_date': '2026-04-30',
                'reason': 'Invalid leave',
            },
            format='json',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('published_professor', response.data)

    def test_personal_key_can_update_and_delete_own_leave(self):
        leave = ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
            reason='One day leave',
        )

        patch_response = self.client.patch(
            f'/professor_leaves/leaves/{leave.id}/?institute={self.institute.id}',
            data={
                'end_date': '2026-05-03',
                'reason': 'Updated leave',
            },
            format='json',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['total_days'], 3)
        self.assertEqual(patch_response.data['reason'], 'Updated leave')

        delete_response = self.client.delete(
            f'/professor_leaves/leaves/{leave.id}/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProfessorLeave.objects.filter(id=leave.id).exists())


class InstituteTotalLeavesApiTests(ProfessorLeavesBaseTestCase):
    def test_admin_can_create_institute_total_leaves(self):
        response = self.client.post(
            f'/professor_leaves/total-leaves/?institute={self.institute.id}',
            data={
                'total_leaves': 12,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['institute'], self.institute.id)
        self.assertEqual(response.data['institute_name'], 'Alpha Institute')
        self.assertEqual(response.data['total_leaves'], 12)

    def test_admin_cannot_create_duplicate_institute_total_leaves(self):
        InstituteTotalLeave.objects.create(
            institute=self.institute,
            total_leaves=10,
        )

        response = self.client.post(
            f'/professor_leaves/total-leaves/?institute={self.institute.id}',
            data={
                'total_leaves': 12,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)

    def test_admin_can_list_and_retrieve_institute_total_leaves(self):
        setting = InstituteTotalLeave.objects.create(
            institute=self.institute,
            total_leaves=14,
        )

        list_response = self.client.get(
            f'/professor_leaves/total-leaves/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['total_leaves'], 14)

        detail_response = self.client.get(
            f'/professor_leaves/total-leaves/{setting.id}/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['institute'], self.institute.id)
        self.assertEqual(detail_response.data['total_leaves'], 14)

    def test_admin_can_update_and_delete_institute_total_leaves(self):
        setting = InstituteTotalLeave.objects.create(
            institute=self.institute,
            total_leaves=8,
        )

        patch_response = self.client.patch(
            f'/professor_leaves/total-leaves/{setting.id}/?institute={self.institute.id}',
            data={
                'total_leaves': 18,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['total_leaves'], 18)

        delete_response = self.client.delete(
            f'/professor_leaves/total-leaves/{setting.id}/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(InstituteTotalLeave.objects.filter(id=setting.id).exists())

    def test_personal_key_can_create_institute_total_leaves(self):
        response = self.client.post(
            f'/professor_leaves/total-leaves/?institute={self.institute.id}',
            data={'total_leaves': 20},
            format='json',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['institute'], self.institute.id)
        self.assertEqual(response.data['total_leaves'], 20)

    def test_personal_key_can_read_update_and_delete_institute_total_leaves(self):
        setting = InstituteTotalLeave.objects.create(
            institute=self.institute,
            total_leaves=16,
        )

        list_response = self.client.get(
            f'/professor_leaves/total-leaves/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['total_leaves'], 16)

        detail_response = self.client.get(
            f'/professor_leaves/total-leaves/{setting.id}/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['total_leaves'], 16)

        patch_response = self.client.patch(
            f'/professor_leaves/total-leaves/{setting.id}/?institute={self.institute.id}',
            data={'total_leaves': 20},
            format='json',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['total_leaves'], 20)

        delete_response = self.client.delete(
            f'/professor_leaves/total-leaves/{setting.id}/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(InstituteTotalLeave.objects.filter(id=setting.id).exists())

    def test_institute_total_leaves_is_shared_for_existing_and_new_professors(self):
        InstituteTotalLeave.objects.create(
            institute=self.institute,
            total_leaves=22,
        )

        new_professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Carol',
            email='carol@example.com',
        )
        ProfessorExperience.objects.create(
            professor=new_professor,
            department='Math',
        )
        professorAdminEmployement.objects.create(
            professor=new_professor,
            personal_id='PROF00000000004',
            employee_id='EMP-4',
        )
        PublishedProfessor.objects.create(
            institute=self.institute,
            source_professor_id=new_professor.id,
            name='Dr Carol',
            email='carol@example.com',
            professor_personal_id='PROF00000000004',
            professor_data={
                'id': new_professor.id,
                'name': 'Dr Carol',
                'email': 'carol@example.com',
                'experience': {
                    'department': 'Math',
                },
            },
        )

        response = self.client.get(
            f'/professor_leaves/total-leaves/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['total_leaves'], 22)
