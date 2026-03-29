from django.urls import path

from .views import (
    EmployeeAccountDetailDetailView,
    EmployeeAccountDetailListCreateView,
)


urlpatterns = [
    path('accounts/', EmployeeAccountDetailListCreateView.as_view(), name='employee-account-detail-list-create'),
    path('accounts/<int:pk>/', EmployeeAccountDetailDetailView.as_view(), name='employee-account-detail-detail'),
]
