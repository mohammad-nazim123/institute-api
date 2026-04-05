from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from iinstitutes_list.models import Institute

from .models import SubordinateAccess, SubordinateAccessVerificationRequest


class SubordinateAccessApiTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Main Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.other_institute = Institute.objects.create(
            name='Other Institute',
            admin_key='b' * 32,
            event_status='active',
        )
        self.headers = {
            'HTTP_X_ADMIN_KEY': self.institute.admin_key,
        }

    def test_admin_can_crud_subordinate_access(self):
        create_response = self.client.post(
            f"{reverse('subordinate-access-list')}?institute={self.institute.id}",
            {
                'post': 'Coordinator',
                'name': 'Rahul',
                'access_control': 'student-management',
                'access_code': 'RAHUL-CODE-01',
            },
            format='json',
            **self.headers,
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['name'], 'Rahul')
        self.assertEqual(create_response.data['institute'], self.institute.id)
        self.assertTrue(create_response.data['is_active'])
        subordinate_id = create_response.data['id']

        list_response = self.client.get(
            f"{reverse('subordinate-access-list')}?institute={self.institute.id}",
            **self.headers,
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['id'], subordinate_id)

        patch_response = self.client.patch(
            f"{reverse('subordinate-access-detail', args=[subordinate_id])}?institute={self.institute.id}",
            {
                'access_control': 'payments',
                'is_active': False,
            },
            format='json',
            **self.headers,
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['access_control'], 'payments')
        self.assertFalse(patch_response.data['is_active'])

        delete_response = self.client.delete(
            f"{reverse('subordinate-access-detail', args=[subordinate_id])}?institute={self.institute.id}",
            **self.headers,
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SubordinateAccess.objects.filter(pk=subordinate_id).exists())

    def test_list_is_scoped_to_authenticated_institute(self):
        SubordinateAccess.objects.create(
            institute=self.institute,
            post='Coordinator',
            name='Main User',
            access_control='students',
            access_code='MAIN-CODE',
            is_active=True,
        )
        SubordinateAccess.objects.create(
            institute=self.other_institute,
            post='Coordinator',
            name='Other User',
            access_control='students',
            access_code='OTHER-CODE',
            is_active=False,
        )

        response = self.client.get(
            f"{reverse('subordinate-access-list')}?institute={self.institute.id}",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Main User')

    def test_access_code_must_be_less_than_40_characters(self):
        response = self.client.post(
            f"{reverse('subordinate-access-list')}?institute={self.institute.id}",
            {
                'post': 'Coordinator',
                'name': 'Rahul',
                'access_control': 'student-management',
                'access_code': 'X' * 40,
            },
            format='json',
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('access_code', response.data)

    def test_requires_32_character_admin_key_in_header(self):
        response = self.client.get(
            f"{reverse('subordinate-access-list')}?institute={self.institute.id}",
            HTTP_X_ADMIN_KEY='short-key',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data['detail'],
            'Admin key must be exactly 32 characters in X-Admin-Key header.',
        )

    def test_rejects_institute_override_in_request_body(self):
        response = self.client.post(
            f"{reverse('subordinate-access-list')}?institute={self.institute.id}",
            {
                'institute': self.other_institute.id,
                'post': 'Coordinator',
                'name': 'Rahul',
                'access_control': 'student-management',
                'access_code': 'RAHUL-CODE-01',
                'is_active': True,
            },
            format='json',
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['institute'][0],
            'Institute does not match the authenticated institute.',
        )

    def test_shorter_admin_key_login_returns_clear_error_for_deactive_subordinate(self):
        subordinate = SubordinateAccess.objects.create(
            institute=self.institute,
            post='Coordinator',
            name='Rahul',
            access_control='student-management',
            access_code='R' * 31,
            is_active=False,
        )

        response = self.client.post(
            reverse('institute-verify'),
            data={
                'name': self.institute.name,
                'admin_key': 'R' * 31,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'This access key is deactive right now. Please contact the Super Admin.')
        self.assertFalse(
            SubordinateAccessVerificationRequest.objects.filter(subordinate_access=subordinate).exists()
        )

    def test_super_admin_can_approve_request_and_mark_subordinate_verified(self):
        subordinate = SubordinateAccess.objects.create(
            institute=self.institute,
            post='Coordinator',
            name='Rahul',
            access_control='student-management',
            access_code='R' * 30,
            is_active=False,
        )
        request_obj = SubordinateAccessVerificationRequest.objects.create(
            institute=self.institute,
            subordinate_access=subordinate,
        )

        list_response = self.client.get(
            reverse('subordinate-access-verification-request-list'),
            HTTP_X_ADMIN_KEY=settings.ADMIN_KEY,
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data[0]['id'], request_obj.id)

        approve_response = self.client.patch(
            reverse('subordinate-access-verification-request-detail', args=[request_obj.id]),
            data={'status': 'approved'},
            format='json',
            HTTP_X_ADMIN_KEY=settings.ADMIN_KEY,
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        request_obj.refresh_from_db()
        subordinate.refresh_from_db()
        self.assertEqual(request_obj.status, SubordinateAccessVerificationRequest.STATUS_APPROVED)
        self.assertTrue(subordinate.is_active)

    def test_approved_subordinate_can_login_from_institute_verify(self):
        subordinate = SubordinateAccess.objects.create(
            institute=self.institute,
            post='Coordinator',
            name='Rahul',
            access_control='student-management',
            access_code='R' * 29,
            is_active=False,
        )
        request_obj = SubordinateAccessVerificationRequest.objects.create(
            institute=self.institute,
            subordinate_access=subordinate,
            status=SubordinateAccessVerificationRequest.STATUS_PENDING,
        )

        self.client.patch(
            reverse('subordinate-access-verification-request-detail', args=[request_obj.id]),
            data={'status': 'approved'},
            format='json',
            HTTP_X_ADMIN_KEY=settings.ADMIN_KEY,
        )

        login_response = self.client.post(
            reverse('institute-verify'),
            data={
                'name': self.institute.name,
                'admin_key': 'R' * 29,
            },
            format='json',
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.data['name'], self.institute.name)
        self.assertEqual(login_response.data['subordinate_access']['name'], 'Rahul')
        self.assertTrue(login_response.data['subordinate_access']['is_active'])

    def test_deactive_subordinate_returns_clear_error_from_institute_verify(self):
        SubordinateAccess.objects.create(
            institute=self.institute,
            post='Coordinator',
            name='Rahul',
            access_control='student-management',
            access_code='R' * 31,
            is_active=False,
        )

        response = self.client.post(
            reverse('institute-verify'),
            data={
                'name': self.institute.name,
                'admin_key': 'R' * 31,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data['detail'],
            'This access key is deactive right now. Please contact the Super Admin.',
        )
