from django.urls import path

from .views import PublishedExamResultDetailView, PublishedExamResultListView


urlpatterns = [
    path('', PublishedExamResultListView.as_view(), name='published-exam-result-list'),
    path('<int:student_id>/', PublishedExamResultDetailView.as_view(), name='published-exam-result-detail'),
]
