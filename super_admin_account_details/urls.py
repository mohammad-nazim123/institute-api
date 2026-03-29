from django.urls import path

from .views import (
    SuperAdminAccountDetailDetailView,
    SuperAdminAccountDetailListCreateView,
)


urlpatterns = [
    path('accounts/', SuperAdminAccountDetailListCreateView.as_view(), name='super-admin-account-detail-list-create'),
    path('accounts/<int:pk>/', SuperAdminAccountDetailDetailView.as_view(), name='super-admin-account-detail-detail'),
]
