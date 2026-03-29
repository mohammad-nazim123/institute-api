from django.urls import path
from .views import CourseView

urlpatterns = [
    path('course/', CourseView.as_view(), name='course-list'),
    path('course/<int:pk>/', CourseView.as_view(), name='course-detail'),
]