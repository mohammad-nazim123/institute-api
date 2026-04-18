from datetime import datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from iinstitutes_list.models import Institute

from .models import ActivityEvent


class ActivityTimelinePaginationTests(APITestCase):
    def setUp(self):
        self.institute = Institute.objects.create(
            name='Timeline Institute',
            admin_key='t' * 32,
            event_status='active',
        )
        self.url = reverse('activity-timeline')
        self.current_timezone = timezone.get_current_timezone()
        self.today = timezone.localdate()
        self.yesterday = self.today - timedelta(days=1)

        self.today_events = [
            self._create_activity(
                title=f'Today Activity {index + 1}',
                occurred_at=self._aware_datetime(self.today, 23, 59 - index),
            )
            for index in range(25)
        ]
        self.yesterday_events = [
            self._create_activity(
                title=f'Yesterday Activity {index + 1}',
                occurred_at=self._aware_datetime(self.yesterday, 21, 59 - index),
            )
            for index in range(3)
        ]

    def _aware_datetime(self, date_value, hour, minute):
        return timezone.make_aware(
            datetime.combine(date_value, time(hour=hour, minute=minute)),
            self.current_timezone,
        )

    def _create_activity(self, *, title, occurred_at):
        return ActivityEvent.objects.create(
            institute=self.institute,
            actor_name='Admin User',
            actor_role='Super Admin',
            actor_access_control='full access',
            actor_source='super_admin',
            action='create',
            entity_type='student',
            entity_id=None,
            entity_name=title,
            title=title,
            description='',
            details={},
            occurred_at=occurred_at,
        )

    def test_timeline_defaults_to_today_and_returns_twenty_items_per_page(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['page_size'], 20)
        self.assertEqual(response.data['total_pages'], 2)
        self.assertEqual(response.data['results']['date'], self.today.isoformat())
        self.assertEqual(len(response.data['results']['timeline']), 20)
        self.assertEqual(response.data['results']['timeline'][0]['title'], 'Today Activity 1')
        self.assertEqual(response.data['results']['timeline'][-1]['title'], 'Today Activity 20')
        self.assertEqual(response.data['results']['latest_id'], self.today_events[0].id)

    def test_timeline_returns_remaining_today_items_on_second_page(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&page=2',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(response.data['page'], 2)
        self.assertEqual(len(response.data['results']['timeline']), 5)
        self.assertEqual(
            [item['title'] for item in response.data['results']['timeline']],
            [
                'Today Activity 21',
                'Today Activity 22',
                'Today Activity 23',
                'Today Activity 24',
                'Today Activity 25',
            ],
        )

    def test_timeline_returns_empty_payload_instead_of_error_when_date_has_no_rows(self):
        empty_date = self.today + timedelta(days=30)

        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&date={empty_date.isoformat()}&page=5',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['results']['date'], empty_date.isoformat())
        self.assertEqual(response.data['results']['timeline'], [])
        self.assertEqual(response.data['results']['latest_id'], 0)

    def test_timeline_filters_by_selected_date(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&date={self.yesterday.isoformat()}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['total_pages'], 1)
        self.assertEqual(response.data['results']['date'], self.yesterday.isoformat())
        self.assertEqual(
            [item['title'] for item in response.data['results']['timeline']],
            [
                'Yesterday Activity 1',
                'Yesterday Activity 2',
                'Yesterday Activity 3',
            ],
        )

    def test_timeline_can_return_all_dates_when_requested(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&all=true&page=2',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 28)
        self.assertEqual(response.data['page'], 2)
        self.assertEqual(response.data['total_pages'], 2)
        self.assertEqual(response.data['results']['scope'], 'all')
        self.assertEqual(response.data['results']['date'], 'all')
        self.assertEqual(
            [item['title'] for item in response.data['results']['timeline']],
            [
                'Today Activity 21',
                'Today Activity 22',
                'Today Activity 23',
                'Today Activity 24',
                'Today Activity 25',
                'Yesterday Activity 1',
                'Yesterday Activity 2',
                'Yesterday Activity 3',
            ],
        )

    def test_timeline_accepts_date_all_alias(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&date=all',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 28)
        self.assertEqual(response.data['results']['scope'], 'all')

    def test_timeline_returns_empty_state_for_out_of_range_page_when_date_has_no_events(self):
        empty_date = (self.today + timedelta(days=7)).isoformat()

        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&date={empty_date}&page=2',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['total_pages'], 1)
        self.assertEqual(response.data['results']['date'], empty_date)
        self.assertEqual(response.data['results']['timeline'], [])
        self.assertEqual(response.data['results']['latest_id'], 0)

    def test_timeline_rejects_invalid_date(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&date=31-03-2026',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'date': ['Enter a valid date in YYYY-MM-DD format.']},
        )
