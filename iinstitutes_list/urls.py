from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'institute', views.InstituteViewSet, basename='institute')

urlpatterns = [
    path('verify/', views.InstituteVerifyView.as_view(), name='institute-verify'),
] + router.urls