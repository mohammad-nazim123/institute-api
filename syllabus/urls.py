from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'course', views.CourseViewSet, basename='course')

urlpatterns = router.urls

# urlpatterns = [
#     # path('syllabus/', SyllabusViewSet.as_view({'get': 'list'})),
# ]