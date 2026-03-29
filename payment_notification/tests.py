from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from institute_api.encryption import ENCRYPTED_VALUE_PREFIX
from professors.models import Professor, ProfessorExperience

from .models import PaymentNotification


class PaymentNotificationApiTests(TestCase):
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
            phone_number='9999999999',
        )
        ProfessorExperience.objects.create(
            professor=self.professor,
            department='CSE',
        )
        self.other_professor = Professor.objects.create(
            institute=self.other_institute,
            name='Dr Eve',
            email='eve@example.com',
            phone_number='8888888888',
        )
        ProfessorExperience.objects.create(
            professor=self.other_professor,
            department='ECE',
        )
        self.url = f'/payment_notifications/employees/?institute={self.institute.id}'

    def test_create_requires_admin_key_header(self):
        response = self.client.post(
            self.url,
            data={
                'professor': self.professor.id,
                'account_holder_name': 'Dr Bob',
                'bank_name': 'State Bank',
                'account_number': '123456789012',
                'ifsc_code': 'SBIN0123456',
                'final_amount': '45000.00',
                'payment_month': '2026-03',
                'payment_date': '2026-03-21',
                'approved_leaves': 2,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_query_param_admin_key_is_rejected(self):
        response = self.client.get(f'{self.url}&admin_key={self.institute.admin_key}')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_full_crud_returns_professor_and_department(self):
        create_response = self.client.post(
            self.url,
            data={
                'professor': self.professor.id,
                'account_holder_name': 'Dr Bob',
                'bank_name': 'State Bank',
                'account_number': '123456789012',
                'ifsc_code': 'SBIN0123456',
                'final_amount': '45000.00',
                'payment_month': '2026-03',
                'payment_date': '2026-03-21',
                'approved_leaves': 2,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['institute'], self.institute.id)
        self.assertEqual(create_response.data['professor'], self.professor.id)
        self.assertEqual(create_response.data['professor_name'], 'Dr Bob')
        self.assertEqual(create_response.data['department'], 'CSE')
        self.assertEqual(create_response.data['final_amount'], '45000.00')
        self.assertEqual(create_response.data['payment_month'], '2026-03')
        self.assertEqual(create_response.data['payment_date'], '2026-03-21')
        self.assertEqual(create_response.data['approved_leaves'], 2)

        stored_row = PaymentNotification.objects.filter(
            pk=create_response.data['id']
        ).values(
            'account_number',
            'ifsc_code',
            'final_amount',
            'payment_date',
        ).get()
        self.assertTrue(stored_row['account_number'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['ifsc_code'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['final_amount'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['payment_date'].startswith(ENCRYPTED_VALUE_PREFIX))

        record_id = create_response.data['id']

        list_response = self.client.get(
            self.url,
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)

        detail_url = f'/payment_notifications/employees/{record_id}/?institute={self.institute.id}'
        patch_response = self.client.patch(
            detail_url,
            data={'approved_leaves': 3, 'final_amount': '42000.00'},
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['approved_leaves'], 3)
        self.assertEqual(patch_response.data['final_amount'], '42000.00')

        delete_response = self.client.delete(
            detail_url,
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(PaymentNotification.objects.count(), 0)

    def test_rejects_professor_from_other_institute(self):
        response = self.client.post(
            self.url,
            data={
                'professor': self.other_professor.id,
                'account_holder_name': 'Dr Eve',
                'bank_name': 'Axis Bank',
                'account_number': '123456789999',
                'ifsc_code': 'UTIB0123456',
                'final_amount': '39000.00',
                'payment_month': '2026-03',
                'payment_date': '2026-03-21',
                'approved_leaves': 1,
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('professor', response.data)

    def test_other_institute_cannot_access_record(self):
        record = PaymentNotification.objects.create(
            institute=self.institute,
            professor=self.professor,
            payment_month_key='2026-03',
            account_holder_name='Dr Bob',
            bank_name='State Bank',
            account_number='123456789012',
            ifsc_code='SBIN0123456',
            final_amount='45000.00',
            payment_month='2026-03',
            payment_date='2026-03-21',
            approved_leaves='2',
        )

        response = self.client.get(
            f'/payment_notifications/employees/{record.id}/?institute={self.other_institute.id}',
            HTTP_X_ADMIN_KEY=self.other_institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
