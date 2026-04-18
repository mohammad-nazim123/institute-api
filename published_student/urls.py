from django.urls import path

from . import views


urlpatterns = [
    path('', views.PublishedStudentListView.as_view(), name='published-student-list'),
    path('lookup-id/', views.PublishedStudentIdLookupView.as_view(), name='published-student-lookup-id'),
    path('portal-bundle/', views.PublishedStudentPortalBundleView.as_view(), name='published-student-portal-bundle'),
    path('publish-student/', views.PublishSingleStudentView.as_view(), name='published-student-single'),
    path('<int:student_id>/', views.PublishedStudentDetailView.as_view(), name='published-student-detail'),
]
