from django.urls import path
from . import views

urlpatterns = [
    path('contact-us/', views.contact_us, name='contact_us'),
    path('send-student-id/', views.send_student_id, name='send_student_id'),
    path('send-professor-id/', views.send_professor_id, name='send_professor_id'),
]
