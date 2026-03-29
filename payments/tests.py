from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from professors.models import Professor, professorAdminEmployement

from .models import ProfessorsPayments


class ProfessorsPaymentsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Alpha Institute',
            admin_key='a' * 32,
        )
        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Bob',
            email='bob@example.com',
            phone_number='9999999999',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='PROF-1',
            employee_id='EMP-1',
        )
        self.payment = ProfessorsPayments.objects.create(
            institute=self.institute,
            professor=self.professor,
            month_year='2026-03',
            payment_amount=5000,
            payment_status='paid',
        )

    def test_list_returns_verified_institute_wrapper(self):
        response = self.client.get(
            f'/admin_payments/professors-payments/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['name'], 'Alpha Institute')
        self.assertEqual(response.data[0]['professors_payments'][0]['month_year'], '2026-03')

    def test_list_uses_two_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/admin_payments/professors-payments/?institute={self.institute.id}',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 2)

    def test_retrieve_uses_two_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f'/admin_payments/professors-payments/{self.payment.id}/?institute={self.institute.id}',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['professors_payments'][0]['id'], self.payment.id)
        self.assertLessEqual(len(queries), 2)

    def test_upsert_update_uses_four_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                f'/admin_payments/upsert/?institute={self.institute.id}',
                data={
                    'institute': self.institute.id,
                    'professor': self.professor.id,
                    'month_year': '2026-03',
                    'payment_amount': 7000,
                    'payment_status': 'paid',
                },
                format='json',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['payment_amount'], 7000)
        self.assertLessEqual(len(queries), 4)

    def test_upsert_create_uses_four_queries_or_less(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                f'/admin_payments/upsert/?institute={self.institute.id}',
                data={
                    'institute': self.institute.id,
                    'professor': self.professor.id,
                    'month_year': '2026-04',
                    'payment_amount': 8000,
                    'payment_status': 'pending',
                },
                format='json',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['month_year'], '2026-04')
        self.assertLessEqual(len(queries), 4)

    def test_serializer_rejects_professor_from_other_institute(self):
        other_institute = Institute.objects.create(
            name='Beta Institute',
            admin_key='b' * 32,
        )
        other_professor = Professor.objects.create(
            institute=other_institute,
            name='Dr Eve',
            email='eve@example.com',
            phone_number='8888888888',
        )

        response = self.client.post(
            f'/admin_payments/professors-payments/?institute={self.institute.id}',
            data={
                'institute': self.institute.id,
                'professor': other_professor.id,
                'month_year': '2026-05',
                'payment_amount': 9000,
                'payment_status': 'pending',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('professor', response.data)
