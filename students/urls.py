from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'students', views.StudentViewSet, basename='students')

urlpatterns = router.urls

urlpatterns += [
    path('look_up_student_id/', views.StudentIdLookUpViewSet.as_view(), name='look_up_student_id'),
    path('verify/', views.StudentVerifyView.as_view(), name='student-verify'),
    path('fetch-by-key/', views.StudentFetchByPersonalKeyView.as_view(), name='student-fetch-by-key'),
    path('syllabus-students/', views.SyllabusStudentsBulkView.as_view(), name='syllabus-students'),
    path('subjects/', views.SubjectsAssignedView.as_view(), name='subjects-list-create'),
    path('subjects/<int:pk>/', views.SubjectsAssignedView.as_view(), name='subjects-detail'),
]
