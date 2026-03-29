from django.urls import path

from .views import (
    ProfessorAttendanceDetailView,
    ProfessorAttendanceListCreateView,
    ProfessorLeaveDetailView,
    ProfessorLeaveListCreateView,
    ProfessorListView,
)


urlpatterns = [
    path('professors/', ProfessorListView.as_view(), name='professor-attendance-professor-list'),
    path('attendance/', ProfessorAttendanceListCreateView.as_view(), name='professor-attendance-list-create'),
    path('attendance/<int:pk>/', ProfessorAttendanceDetailView.as_view(), name='professor-attendance-detail'),
    path('leaves/', ProfessorLeaveListCreateView.as_view(), name='professor-leave-list-create'),
    path('leaves/<int:pk>/', ProfessorLeaveDetailView.as_view(), name='professor-leave-detail'),
]
