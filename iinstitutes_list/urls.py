from django.urls import include, path
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'institute', views.InstituteViewSet, basename='institute')

urlpatterns = [
    path('verify/', views.InstituteVerifyView.as_view(), name='institute-verify'),
    path('published_schedules/', include('published_schedules.urls')),
    path('published_schedule/', include('published_schedules.urls')),
] + router.urls
