from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from iinstitutes_list.models import Institute
from students.models import Student, StudentSystemDetails
from subordinate_access.models import SubordinateAccess

from .models import DefaultActivity, get_default_session_year


class DefaultActivityApiTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            institute_name='Main Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.other_institute = Institute.objects.create(
            institute_name='Other Institute',
            admin_key='b' * 32,
            event_status='active',
        )
        self.list_url = reverse('default-activity-list-create')

    def test_admin_can_crud_default_activity(self):
        session_year = get_default_session_year()
        create_response = self.client.post(
            f'{self.list_url}?institute={self.institute.id}',
            {
                'session_month': 'jan-dec',
                'session_year': session_year,
                'opening_time': '08:00 AM',
                'closing_time': '04:00 PM',
                'total_yearly_leaves': 50,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['session_month'], 'Jan-Dec')
        self.assertEqual(create_response.data['session_year'], session_year)
        self.assertEqual(create_response.data['opening_time'], '08:00 AM')
        self.assertEqual(create_response.data['closing_time'], '04:00 PM')
        self.assertEqual(create_response.data['total_yearly_leaves'], 50)
        default_activity_id = create_response.data['id']

        patch_response = self.client.patch(
            f"{reverse('default-activity-detail', args=[default_activity_id])}?institute={self.institute.id}",
            {'total_yearly_leaves': 55},
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['total_yearly_leaves'], 55)

        delete_response = self.client.delete(
            f"{reverse('default-activity-detail', args=[default_activity_id])}?institute={self.institute.id}",
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DefaultActivity.objects.filter(pk=default_activity_id).exists())

    def test_session_year_must_be_one_of_next_10_academic_years(self):
        current_start_year = int(get_default_session_year().split('-')[0])
        too_far_session_year = f'{current_start_year + 10}-{current_start_year + 11}'

        response = self.client.post(
            f'{self.list_url}?institute={self.institute.id}',
            {
                'session_month': 'Jan-Dec',
                'session_year': too_far_session_year,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('session_year', response.data)

    def test_write_requires_exact_32_character_admin_key(self):
        SubordinateAccess.objects.create(
            institute=self.institute,
            post='Coordinator',
            name='Rahul',
            access_control='student access',
            access_code='R' * 31,
            is_active=True,
        )

        response = self.client.post(
            f'{self.list_url}?institute={self.institute.id}',
            {'session_month': 'Jan-Dec'},
            format='json',
            HTTP_X_ADMIN_KEY='R' * 31,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_accepts_32_31_30_29_and_15_character_keys(self):
        default_activity = DefaultActivity.objects.create(
            institute=self.institute,
            session_month='Jan-Dec',
        )

        access_codes = ['R' * 31, 'S' * 30, 'T' * 29]
        for access_code in access_codes:
            SubordinateAccess.objects.create(
                institute=self.institute,
                post='Coordinator',
                name=f'User {len(access_code)}',
                access_control='student access',
                access_code=access_code,
                is_active=True,
            )

        admin_response = self.client.get(
            f'{self.list_url}?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.data[0]['id'], default_activity.id)

        for access_code in access_codes:
            response = self.client.get(
                f'{self.list_url}?institute={self.institute.id}',
                HTTP_X_ADMIN_KEY=access_code,
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data[0]['id'], default_activity.id)

        student = Student.objects.create(
            institute=self.institute,
            name='Student One',
        )
        StudentSystemDetails.objects.create(
            student=student,
            student_personal_id='P' * 15,
        )

        personal_response = self.client.get(
            f'{self.list_url}?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='P' * 15,
        )

        self.assertEqual(personal_response.status_code, status.HTTP_200_OK)
        self.assertEqual(personal_response.data[0]['id'], default_activity.id)

    def test_list_is_scoped_to_authenticated_institute(self):
        DefaultActivity.objects.create(
            institute=self.institute,
            session_month='Jan-Dec',
        )
        DefaultActivity.objects.create(
            institute=self.other_institute,
            session_month='Apr-Mar',
        )

        response = self.client.get(
            f'{self.list_url}?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['institute'], self.institute.id)
