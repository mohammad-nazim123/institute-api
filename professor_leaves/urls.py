from django.urls import path

from .views import (
    InstituteTotalLeaveDetailView,
    InstituteTotalLeaveListCreateView,
    ProfessorLeaveDetailView,
    ProfessorLeaveListCreateView,
)


urlpatterns = [
    path('leaves/', ProfessorLeaveListCreateView.as_view(), name='professor-leave-list-create'),
    path('leaves/<int:pk>/', ProfessorLeaveDetailView.as_view(), name='professor-leave-detail'),
    path('total-leaves/', InstituteTotalLeaveListCreateView.as_view(), name='institute-total-leave-list-create'),
    path('total-leaves/<int:pk>/', InstituteTotalLeaveDetailView.as_view(), name='institute-total-leave-detail'),
]
