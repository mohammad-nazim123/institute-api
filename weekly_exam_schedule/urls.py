from django.urls import path

from . import views


urlpatterns = [
    path('', views.WeeklyExamScheduleDictionaryView.as_view(), name='weekly-exam-schedule-dictionary'),
    path('bulk/', views.WeeklyExamScheduleBulkView.as_view(), name='weekly-exam-schedule-bulk'),
    path('workspace/', views.WeeklyExamScheduleWorkspaceView.as_view(), name='weekly-exam-schedule-workspace'),
    path('references/', views.WeeklyExamScheduleReferencesView.as_view(), name='weekly-exam-schedule-references'),
    path('weekly/', views.WeeklyScheduleEntryView.as_view(), name='weekly-exam-weekly-list-create'),
    path('weekly/<int:pk>/', views.WeeklyScheduleEntryView.as_view(), name='weekly-exam-weekly-detail'),
    path('exam/', views.ExamScheduleEntryView.as_view(), name='weekly-exam-exam-list-create'),
    path('exam/<int:pk>/', views.ExamScheduleEntryView.as_view(), name='weekly-exam-exam-detail'),
]
