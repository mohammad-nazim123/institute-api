from django.urls import path
from .views import (
    AttendanceDetailView,
    AttendanceListCreateView,
    MarkAttendanceView,
    StudentAttendanceBulkView,
    StudentAttendanceSummaryView,
    StudentAttendanceView,
    StudentListView,
)

urlpatterns = [
    path('students/', StudentListView.as_view(), name='student-list'),
    path('students/attendance/', StudentAttendanceBulkView.as_view(), name='students-attendance-bulk'),
    path('attendance/students/summary/', StudentAttendanceSummaryView.as_view(), name='students-attendance-summary'),
    path('attendance/records/', AttendanceListCreateView.as_view(), name='attendance-record-list-create'),
    path('attendance/records/<int:pk>/', AttendanceDetailView.as_view(), name='attendance-record-detail'),
    path('attendance/mark/', MarkAttendanceView.as_view(), name='mark-attendance'),
    path('attendance/student/<int:student_id>/', StudentAttendanceView.as_view(), name='student-attendance'),
]
