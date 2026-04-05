from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import (
    SubordinateAccessViewSet,
    SubordinateAccessVerificationRequestDetailView,
    SubordinateAccessVerificationRequestListView,
)


router = DefaultRouter()
router.register(r'subordinate-access', SubordinateAccessViewSet, basename='subordinate-access')

urlpatterns = router.urls + [
    path(
        'verification-requests/',
        SubordinateAccessVerificationRequestListView.as_view(),
        name='subordinate-access-verification-request-list',
    ),
    path(
        'verification-requests/<int:pk>/',
        SubordinateAccessVerificationRequestDetailView.as_view(),
        name='subordinate-access-verification-request-detail',
    ),
]
