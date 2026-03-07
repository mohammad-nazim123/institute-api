from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'weekly', views.WeeklyScheduleViewSet, basename='weekly')
router.register(r'exam', views.ExamScheduleViewSet, basename='exam')
router.register(r'weekly-day', views.WeeklyScheduleDayViewSet, basename='weekly-day')
router.register(r'exam-date', views.ExamScheduleDateViewSet, basename='exam-date')

urlpatterns = router.urls

# urlpatterns = [
#     # path('', views.schedule_list, name='schedule_list'),
# ]