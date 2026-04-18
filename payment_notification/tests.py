from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from default_activities.models import DefaultActivity
from iinstitutes_list.models import Institute
from institute_api.encryption import ENCRYPTED_VALUE_PREFIX
from professor_leaves.models import ProfessorLeave
from professors.models import Professor, ProfessorExperience, professorAdminEmployement
from published_professors.models import PublishedProfessor

from .models import PaymentNotification


def extract_results(data):
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


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
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='PROF00000000001',
            employee_id='EMP-1',
        )
        self.second_professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Alice',
            email='alice@example.com',
            phone_number='7777777777',
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
        professorAdminEmployement.objects.create(
            professor=self.other_professor,
            personal_id='PROF00000000002',
            employee_id='EMP-2',
        )
        self.url = f'/payment_notifications/employees/?institute={self.institute.id}'
        self.summary_url = (
            f'/payment_notifications/employees/summary/?institute={self.institute.id}'
        )

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

    def test_list_requires_institute_access_key(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_full_crud_returns_professor_department_employee_and_amount_fields(self):
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
        self.assertEqual(create_response.data['employee_id'], 'EMP-1')
        self.assertEqual(create_response.data['gross_amount'], '45000.00')
        self.assertEqual(create_response.data['deducted_amount'], '0.00')
        self.assertEqual(create_response.data['final_amount'], '45000.00')
        self.assertEqual(create_response.data['payment_month'], '2026-03')
        self.assertEqual(create_response.data['payment_date'], '2026-03-21')
        self.assertEqual(create_response.data['approved_leaves'], 2)
        self.assertEqual(create_response.data['status'], 'pending')

        stored_row = PaymentNotification.objects.filter(
            pk=create_response.data['id']
        ).values(
            'account_number',
            'ifsc_code',
            'gross_amount',
            'deducted_amount',
            'final_amount',
            'payment_date',
        ).get()
        self.assertTrue(stored_row['account_number'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['ifsc_code'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['gross_amount'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['deducted_amount'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['final_amount'].startswith(ENCRYPTED_VALUE_PREFIX))
        self.assertTrue(stored_row['payment_date'].startswith(ENCRYPTED_VALUE_PREFIX))

        record_id = create_response.data['id']

        list_response = self.client.get(
            self.url,
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        list_results = extract_results(list_response.data)
        self.assertEqual(len(list_results), 1)
        self.assertEqual(list_results[0]['employee_id'], 'EMP-1')

        detail_url = f'/payment_notifications/employees/{record_id}/?institute={self.institute.id}'
        patch_response = self.client.patch(
            detail_url,
            data={
                'approved_leaves': 3,
                'gross_amount': '50000.00',
                'deducted_amount': '8000.00',
                'final_amount': '42000.00',
                'status': 'approved',
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['approved_leaves'], 3)
        self.assertEqual(patch_response.data['gross_amount'], '50000.00')
        self.assertEqual(patch_response.data['deducted_amount'], '8000.00')
        self.assertEqual(patch_response.data['final_amount'], '42000.00')
        self.assertEqual(patch_response.data['status'], 'approved')

        delete_response = self.client.delete(
            detail_url,
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(PaymentNotification.objects.count(), 0)

    def test_summary_endpoint_returns_card_ready_rows_and_filters(self):
        DefaultActivity.objects.create(
            institute=self.institute,
            total_yearly_leaves=2,
        )
        published_professor = PublishedProfessor.objects.create(
            institute=self.institute,
            source_professor_id=self.professor.id,
            name=self.professor.name,
            email=self.professor.email,
            professor_personal_id='PROF00000000001',
            professor_data={
                'id': self.professor.id,
                'name': self.professor.name,
                'experience': {
                    'department': 'CSE',
                },
            },
        )

        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 3, 30),
            end_date=date(2026, 4, 2),
            reason='Conference',
            leaves_status=ProfessorLeave.LeaveStatus.ACCEPTED,
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 5, 10),
            end_date=date(2026, 5, 12),
            reason='Medical',
            leaves_status=ProfessorLeave.LeaveStatus.ACCEPTED,
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=published_professor,
            professor_name='Dr Bob',
            department='CSE',
            email='bob@example.com',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 1),
            reason='Pending leave',
            leaves_status=ProfessorLeave.LeaveStatus.PENDING,
        )

        april_notification = PaymentNotification.objects.create(
            institute=self.institute,
            professor=self.professor,
            payment_month_key='2026-04',
            account_holder_name='Dr Bob',
            bank_name='State Bank',
            account_number='123456789012',
            ifsc_code='SBIN0123456',
            gross_amount='50000.00',
            deducted_amount='0.00',
            final_amount='50000.00',
            payment_month='2026-04',
            payment_date='2026-04-30',
            approved_leaves='2',
            status=PaymentNotification.Status.PENDING,
        )
        may_notification = PaymentNotification.objects.create(
            institute=self.institute,
            professor=self.professor,
            payment_month_key='2026-05',
            account_holder_name='Dr Bob',
            bank_name='State Bank',
            account_number='123456789012',
            ifsc_code='SBIN0123456',
            gross_amount='50000.00',
            deducted_amount='6000.00',
            final_amount='44000.00',
            payment_month='2026-05',
            payment_date='2026-05-31',
            approved_leaves='3',
            status=PaymentNotification.Status.APPROVED,
        )
        second_notification = PaymentNotification.objects.create(
            institute=self.institute,
            professor=self.second_professor,
            payment_month_key='2026-05',
            account_holder_name='Dr Alice',
            bank_name='Axis Bank',
            account_number='999999999999',
            ifsc_code='UTIB0123456',
            gross_amount='47000.00',
            deducted_amount='0.00',
            final_amount='47000.00',
            payment_month='2026-05',
            payment_date='2026-05-31',
            approved_leaves='0',
            status=PaymentNotification.Status.REJECTED,
        )

        summary_response = self.client.get(
            self.summary_url,
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(summary_response.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_response.data['total_count'], 3)
        self.assertEqual(summary_response.data['count'], 3)
        self.assertEqual(summary_response.data['institute_total_leaves'], 2)

        rows_by_month = {
            (row['professor'], row['payment_month']): row
            for row in summary_response.data['results']
        }
        april_row = rows_by_month[(april_notification.professor_id, '2026-04')]
        may_row = rows_by_month[(may_notification.professor_id, '2026-05')]
        second_row = rows_by_month[(second_notification.professor_id, '2026-05')]

        self.assertEqual(april_row['employee_id'], 'EMP-1')
        self.assertEqual(april_row['payment_month_leaves'], 2)
        self.assertEqual(april_row['accepted_leaves_till_month'], 4)
        self.assertEqual(april_row['remaining_leaves'], 0)
        self.assertEqual(april_row['extra_leaves_this_month'], 2)
        self.assertEqual(april_row['gross_amount'], '50000.00')
        self.assertEqual(april_row['deducted_amount'], '0.00')
        self.assertEqual(april_row['final_amount'], '50000.00')

        self.assertEqual(may_row['payment_month_leaves'], 3)
        self.assertEqual(may_row['accepted_leaves_till_month'], 7)
        self.assertEqual(may_row['remaining_leaves'], 0)
        self.assertEqual(may_row['extra_leaves_this_month'], 3)
        self.assertEqual(may_row['status'], 'approved')
        self.assertEqual(may_row['deducted_amount'], '6000.00')
        self.assertEqual(may_row['amount_per_day'], '1643.84')

        self.assertEqual(second_row['employee_id'], 'EMP-3')
        self.assertEqual(second_row['status'], 'rejected')
        self.assertEqual(second_row['payment_month_leaves'], 0)

        approved_response = self.client.get(
            f'{self.summary_url}&status=approved',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(approved_response.status_code, status.HTTP_200_OK)
        self.assertEqual(approved_response.data['total_count'], 3)
        self.assertEqual(approved_response.data['count'], 1)
        self.assertEqual(approved_response.data['results'][0]['id'], may_notification.id)

        search_response = self.client.get(
            f'{self.summary_url}&search=EMP-1',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(search_response.data['total_count'], 3)
        self.assertEqual(search_response.data['count'], 2)
        self.assertEqual(
            {row['id'] for row in search_response.data['results']},
            {april_notification.id, may_notification.id},
        )

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
            gross_amount='45000.00',
            deducted_amount='0.00',
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
