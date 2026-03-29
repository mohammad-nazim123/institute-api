from django.urls import path

from . import views


urlpatterns = [
    path('weekly/', views.PublishedWeeklyScheduleView.as_view(), name='published-schedules-weekly-list-create'),
    path('weekly/<int:pk>/', views.PublishedWeeklyScheduleView.as_view(), name='published-schedules-weekly-detail'),
    path('weekly/publish/', views.PublishedWeeklySchedulePublishView.as_view(), name='published-schedules-weekly-publish'),
    path('exam/', views.PublishedExamScheduleView.as_view(), name='published-schedules-exam-list-create'),
    path('exam/<int:pk>/', views.PublishedExamScheduleView.as_view(), name='published-schedules-exam-detail'),
    path('exam/publish/', views.PublishedExamSchedulePublishView.as_view(), name='published-schedules-exam-publish'),
]
