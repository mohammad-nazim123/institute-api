from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'professors-payments', views.ProfessorsPaymentsViewSet, basename='professors-payments')

urlpatterns = router.urls + [
    path('upsert/', views.ProfessorPaymentUpsertView.as_view(), name='professor-payment-upsert'),
]