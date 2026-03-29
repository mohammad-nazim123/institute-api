from django.urls import path

from . import views


urlpatterns = [
    path('', views.PublishedStudentListView.as_view(), name='published-student-list'),
    path('lookup-id/', views.PublishedStudentIdLookupView.as_view(), name='published-student-lookup-id'),
    path('<int:student_id>/', views.PublishedStudentDetailView.as_view(), name='published-student-detail'),
]
