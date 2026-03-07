import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'institute_api.settings')
django.setup()

from django.test import Client
import json

client = Client()
data = {
    'email': 'test@example.com',
    'password': 'TestPass123!',
    'password2': 'TestPass123!'
}

response = client.post('/auth/sign_up/', data=json.dumps(data), content_type='application/json')
print(f"Status: {response.status_code}")
print(f"Content-Type: {response.get('Content-Type', 'N/A')}")
print(f"Response: {response.content.decode()[:500]}")
