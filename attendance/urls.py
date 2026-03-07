from django.urls import path
from .views import StudentListView, MarkAttendanceView, StudentAttendanceView

urlpatterns = [
    path('students/', StudentListView.as_view(), name='student-list'),
    path('attendance/mark/', MarkAttendanceView.as_view(), name='mark-attendance'),
    path('attendance/student/<int:student_id>/', StudentAttendanceView.as_view(), name='student-attendance'),
]
