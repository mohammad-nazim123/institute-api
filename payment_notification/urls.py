from django.urls import path

from .views import PaymentNotificationDetailView, PaymentNotificationListCreateView


urlpatterns = [
    path('employees/', PaymentNotificationListCreateView.as_view(), name='payment-notification-list-create'),
    path('employees/<int:pk>/', PaymentNotificationDetailView.as_view(), name='payment-notification-detail'),
]
