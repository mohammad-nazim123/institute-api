from django.urls import path
from . import views

urlpatterns = [
    # Exam data CRUD — flat, scoped by class + branch + academic_term
    path('', views.ExamDataView.as_view(), name='exam-data-list-create'),
    path('<int:pk>/', views.ExamDataView.as_view(), name='exam-data-detail'),

    # Obtained marks CRUD
    path('marks/', views.ObtainedMarksView.as_view(), name='obtained-marks-list-create'),
    path('marks/<int:pk>/', views.ObtainedMarksView.as_view(), name='obtained-marks-detail'),
]
