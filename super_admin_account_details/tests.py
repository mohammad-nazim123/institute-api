from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from institute_api.encryption import ENCRYPTED_VALUE_PREFIX

from .models import SuperAdminAccountDetail


class SuperAdminAccountDetailApiTests(TestCase):
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
        self.admin_key = self.institute.admin_key
        self.other_admin_key = self.other_institute.admin_key
        self.url = f'/super_admin_account_details/accounts/?institute={self.institute.id}'

    def test_create_requires_valid_admin_key_header(self):
        response = self.client.post(
            self.url,
            data={
                'account_holder_name': 'Main Admin',
                'bank_name': 'State Bank',
                'account_number': '123456789012',
                'ifsc_code': 'sbin0123456',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_query_param_admin_key_is_rejected(self):
        response = self.client.get(f'{self.url}&admin_key={self.admin_key}')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_super_admin_account_detail_full_crud_inside_institute(self):
        create_response = self.client.post(
            self.url,
            data={
                'account_holder_name': 'Main Admin',
                'bank_name': 'State Bank',
                'account_number': '123456789012',
                'ifsc_code': 'sbin0123456',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.admin_key,
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['institute'], self.institute.id)
        self.assertEqual(create_response.data['account_holder_name'], 'Main Admin')
        self.assertEqual(create_response.data['bank_name'], 'State Bank')
        self.assertEqual(create_response.data['account_number'], '123456789012')
        self.assertEqual(create_response.data['ifsc_code'], 'SBIN0123456')

        stored_row = SuperAdminAccountDetail.objects.filter(
            pk=create_response.data['id']
        ).values(
            'account_holder_name',
            'bank_name',
            'account_number',
            'ifsc_code',
        ).get()
        self.assertNotEqual(stored_row['account_number'], '123456789012')
        self.assertTrue(stored_row['account_number'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['ifsc_code'].startswith(ENCRYPTED_VALUE_PREFIX))

        stored_instance = SuperAdminAccountDetail.objects.get(pk=create_response.data['id'])
        self.assertEqual(stored_instance.account_holder_name, 'Main Admin')
        self.assertEqual(stored_instance.account_number, '123456789012')

        record_id = create_response.data['id']

        list_response = self.client.get(
            self.url,
            HTTP_X_ADMIN_KEY=self.admin_key,
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)

        detail_url = f'/super_admin_account_details/accounts/{record_id}/?institute={self.institute.id}'
        patch_response = self.client.patch(
            detail_url,
            data={'bank_name': 'HDFC Bank'},
            format='json',
            HTTP_X_ADMIN_KEY=self.admin_key,
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['bank_name'], 'HDFC Bank')

        delete_response = self.client.delete(
            detail_url,
            HTTP_X_ADMIN_KEY=self.admin_key,
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(SuperAdminAccountDetail.objects.count(), 0)

    def test_other_institute_cannot_access_record(self):
        record = SuperAdminAccountDetail.objects.create(
            institute=self.institute,
            account_holder_name='Main Admin',
            bank_name='State Bank',
            account_number='123456789012',
            ifsc_code='SBIN0123456',
        )

        response = self.client.get(
            f'/super_admin_account_details/accounts/{record.id}/?institute={self.other_institute.id}',
            HTTP_X_ADMIN_KEY=self.other_admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
