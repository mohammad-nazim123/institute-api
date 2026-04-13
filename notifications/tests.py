from django.core import mail
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CONTACT_US_RECIPIENT_EMAIL='owner@example.com',
    CONTACT_US_FROM_EMAIL='support@example.com',
    CONTACT_US_FROM_NAME='educonnectz',
)
class ContactUsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/notifications/contact-us/'

    def test_contact_message_is_sent_to_configured_inbox(self):
        response = self.client.post(
            self.url,
            data={
                'email': 'admin.user@example.com',
                'message': 'Please help me with admin access login.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['message'], 'Contact request sent successfully')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner@example.com'])
        self.assertEqual(mail.outbox[0].reply_to, ['admin.user@example.com'])
        self.assertEqual(mail.outbox[0].from_email, 'educonnectz <support@example.com>')
        self.assertIn('Please help me with admin access login.', mail.outbox[0].body)

    def test_contact_message_requires_valid_email(self):
        response = self.client.post(
            self.url,
            data={
                'email': 'not-an-email',
                'message': 'Please help.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error'], 'Enter a valid email address')
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_message_requires_body_text(self):
        response = self.client.post(
            self.url,
            data={
                'email': 'admin.user@example.com',
                'message': '   ',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error'], "'message' is required")
        self.assertEqual(len(mail.outbox), 0)
