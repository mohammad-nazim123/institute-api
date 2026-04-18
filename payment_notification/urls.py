from django.urls import path

from .views import (
    PaymentNotificationDetailView,
    PaymentNotificationListCreateView,
    PaymentNotificationSummaryView,
)


urlpatterns = [
    path('employees/', PaymentNotificationListCreateView.as_view(), name='payment-notification-list-create'),
    path('employees/summary/', PaymentNotificationSummaryView.as_view(), name='payment-notification-summary'),
    path('employees/<int:pk>/', PaymentNotificationDetailView.as_view(), name='payment-notification-detail'),
]
