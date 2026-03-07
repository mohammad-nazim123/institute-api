from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'student-unique-id', views.StudentUniqueIdViewSet, basename='student-unique-id')
# router.register(r'professor-unique-id', views.ProfessorUniqueIdViewSet, basename='professor-unique-id')

urlpatterns = router.urls

# urlpatterns = [
#     path('unique-ids/', views.UniqueIdsViewSet.as_view({'get': 'list'})),
# ]