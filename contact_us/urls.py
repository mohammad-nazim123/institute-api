from django.urls import path
from . import views

urlpatterns = [
    path('send/', views.contact_us, name='contact_us_send'),
]
