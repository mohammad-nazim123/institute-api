from django.test import TestCase
from rest_framework.test import APIClient

from iinstitutes_list.models import Institute
from professors.models import (
    Professor,
    ProfessorAddress,
    ProfessorExperience,
    ProfessorQualification,
    professorAdminEmployement,
    professorClassAssigned,
)

from .models import PublishedProfessor


class PublishedProfessorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Alpha Institute',
            admin_key='a' * 32,
        )
        self.professor = self.create_professor(
            name='Dr Bob',
            email='bob@example.com',
            personal_id='PROF00000000001',
            employee_id='EMP-1',
            department='CSE',
        )

    def create_professor(self, name, email, personal_id, employee_id, department):
        professor = Professor.objects.create(
            institute=self.institute,
            name=name,
            father_name='Father',
            mother_name='Mother',
            gender='Male',
            phone_number='9999999999',
            email=email,
            indentity_number='AADHAR-1',
            marital_status='Single',
        )
        ProfessorAddress.objects.create(
            professor=professor,
            current_address='Current address',
            permanent_address='Permanent address',
            city='Kolkata',
            state='West Bengal',
            country='India',
        )
        ProfessorQualification.objects.bulk_create([
            ProfessorQualification(
                professor=professor,
                degree='M.Tech',
                institution='IIT',
                year_of_passing='2015',
                percentage='80',
                specialization='CSE',
            ),
            ProfessorQualification(
                professor=professor,
                degree='PhD',
                institution='NIT',
                year_of_passing='2020',
                percentage='85',
                specialization='AI',
            ),
        ])
        ProfessorExperience.objects.create(
            professor=professor,
            designation='Assistant Professor',
            department=department,
            teaching_subject='Python',
            teaching_experience='5',
            interest='Research',
        )
        professorAdminEmployement.objects.create(
            professor=professor,
            personal_id=personal_id,
            employee_id=employee_id,
            employement_type='Full Time',
            working_hours='8',
            salary='50000',
        )
        professorClassAssigned.objects.create(
            professor=professor,
            assigned_course='B.Tech',
            assigned_section='A',
            assigned_year='3',
            session='2025-2026',
        )
        return professor

    def publish_all(self):
        return self.client.post(
            f'/published_professors/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

    def test_publish_transfers_professor_snapshot(self):
        response = self.publish_all()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(len(response.data['published_professors']), 1)
        published = response.data['published_professors'][0]
        self.assertEqual(published['professor_id'], self.professor.id)
        self.assertEqual(published['email'], 'bob@example.com')
        self.assertEqual(published['professor_data']['address']['city'], 'Kolkata')
        self.assertEqual(len(published['professor_data']['qualification']), 2)
        self.assertEqual(
            published['professor_data']['admin_employement']['personal_id'],
            'PROF00000000001',
        )

    def test_professor_bulk_list_returns_unpaginated_professors_and_filters_department(self):
        second_professor = self.create_professor(
            name='Dr Ada',
            email='ada@example.com',
            personal_id='PROF00000000002',
            employee_id='EMP-2',
            department='AI',
        )

        response = self.client.get(
            f'/professors/professors/bulk/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(
            {professor['id'] for professor in response.data['professors']},
            {self.professor.id, second_professor.id},
        )

        filtered_response = self.client.get(
            f'/professors/professors/bulk/?institute={self.institute.id}&department=AI',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual(len(filtered_response.data['professors']), 1)
        self.assertEqual(filtered_response.data['professors'][0]['id'], second_professor.id)

    def test_selected_bulk_publish_creates_only_requested_professors(self):
        second_professor = self.create_professor(
            name='Dr Ada',
            email='ada@example.com',
            personal_id='PROF00000000002',
            employee_id='EMP-2',
            department='AI',
        )

        response = self.client.post(
            f'/published_professors/?institute={self.institute.id}',
            data={'professor_ids': [self.professor.id]},
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(response.data['updated_count'], 0)
        self.assertEqual(response.data['already_exists_count'], 0)
        self.assertEqual(response.data['deleted_count'], 0)
        self.assertEqual(len(response.data['published_professors']), 1)
        self.assertTrue(
            PublishedProfessor.objects.filter(
                institute=self.institute,
                source_professor_id=self.professor.id,
            ).exists()
        )
        self.assertFalse(
            PublishedProfessor.objects.filter(
                institute=self.institute,
                source_professor_id=second_professor.id,
            ).exists()
        )

    def test_selected_bulk_publish_updates_skips_and_preserves_unselected_rows(self):
        second_professor = self.create_professor(
            name='Dr Ada',
            email='ada@example.com',
            personal_id='PROF00000000002',
            employee_id='EMP-2',
            department='AI',
        )
        self.publish_all()

        self.professor.name = 'Dr Robert'
        self.professor.save(update_fields=['name'])

        response = self.client.post(
            f'/published_professors/?institute={self.institute.id}',
            data={'professor_ids': [self.professor.id, second_professor.id]},
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 0)
        self.assertEqual(response.data['updated_count'], 1)
        self.assertEqual(response.data['already_exists_count'], 1)
        self.assertEqual(response.data['deleted_count'], 0)
        self.assertEqual(response.data['already_exists_professor_ids'], [second_professor.id])
        self.assertEqual(
            PublishedProfessor.objects.filter(institute=self.institute).count(),
            2,
        )
        self.assertTrue(
            PublishedProfessor.objects.filter(
                institute=self.institute,
                source_professor_id=second_professor.id,
            ).exists()
        )
        self.assertEqual(
            PublishedProfessor.objects.get(
                institute=self.institute,
                source_professor_id=self.professor.id,
            ).name,
            'Dr Robert',
        )

    def test_publish_single_professor_returns_already_available_when_unchanged(self):
        first_response = self.client.post(
            f'/published_professors/?institute={self.institute.id}&professor_id={self.professor.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.data['created_count'], 1)

        second_response = self.client.post(
            f'/published_professors/?institute={self.institute.id}&professor_id={self.professor.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data['created_count'], 0)
        self.assertEqual(second_response.data['updated_count'], 0)
        self.assertEqual(second_response.data['already_exists_count'], 1)
        self.assertEqual(second_response.data['message'], 'This professor is already available.')
        self.assertEqual(second_response.data['detail'], 'This professor is already available.')
        self.assertEqual(second_response.data['already_exists_professor_ids'], [self.professor.id])

    def test_publish_single_professor_updates_snapshot_when_source_changes(self):
        self.client.post(
            f'/published_professors/?institute={self.institute.id}&professor_id={self.professor.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.professor.name = 'Dr Robert'
        self.professor.save(update_fields=['name'])
        self.professor.experience.department = 'AI'
        self.professor.experience.save(update_fields=['department'])

        response = self.client.post(
            f'/published_professors/?institute={self.institute.id}&professor_id={self.professor.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 0)
        self.assertEqual(response.data['updated_count'], 1)
        self.assertEqual(response.data['already_exists_count'], 0)
        self.assertEqual(response.data['published_professors'][0]['name'], 'Dr Robert')
        self.assertEqual(
            response.data['published_professors'][0]['professor_data']['experience']['department'],
            'AI',
        )

    def test_lookup_id_by_email_and_personal_key_returns_professor_id(self):
        self.publish_all()

        response = self.client.post(
            f'/published_professors/lookup-id/?institute={self.institute.id}',
            data={'email': 'bob@example.com'},
            format='json',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['professor_id'], self.professor.id)

    def test_fetch_by_professor_id_returns_snapshot(self):
        self.publish_all()

        response = self.client.get(
            f'/published_professors/{self.professor.id}/?institute={self.institute.id}',
            HTTP_X_PERSONAL_KEY='PROF00000000001',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.institute.id)
        self.assertEqual(response.data['published_professors'][0]['professor_id'], self.professor.id)
        self.assertEqual(
            response.data['published_professors'][0]['professor_data']['experience']['department'],
            'CSE',
        )

    def test_publish_requires_32_char_admin_key(self):
        response = self.client.post(
            f'/published_professors/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY='SHORTKEY',
        )

        self.assertEqual(response.status_code, 403)

    def test_lookup_requires_15_char_personal_key(self):
        self.publish_all()

        response = self.client.post(
            f'/published_professors/lookup-id/?institute={self.institute.id}',
            data={'email': 'bob@example.com'},
            format='json',
            HTTP_X_PERSONAL_KEY='SHORTKEY',
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_patch_updates_published_snapshot(self):
        self.publish_all()

        response = self.client.patch(
            f'/published_professors/{self.professor.id}/?institute={self.institute.id}',
            data={
                'name': 'Published Dr Bob',
                'email': 'published@example.com',
                'professor_data': {
                    'id': self.professor.id,
                    'name': 'Published Dr Bob',
                },
            },
            format='json',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['published_professors'][0]['name'], 'Published Dr Bob')
        self.assertEqual(response.data['published_professors'][0]['email'], 'published@example.com')

    def test_admin_delete_removes_published_snapshot(self):
        self.publish_all()

        response = self.client.delete(
            f'/published_professors/{self.professor.id}/?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deleted_professor_id'], self.professor.id)
        self.assertFalse(
            PublishedProfessor.objects.filter(
                institute=self.institute,
                source_professor_id=self.professor.id,
            ).exists()
        )
