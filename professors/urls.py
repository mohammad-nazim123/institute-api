from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'professors', views.ProfessorViewSet, basename='professor')

urlpatterns = router.urls

urlpatterns += [
    path('lookup_professor_id/', views.ProfessorIdLookUpAPIView.as_view(), name='lookup_professor_id'),
    path('verify/', views.ProfessorVerifyView.as_view(), name='professor-verify'),
    path('fetch-by-key/', views.ProfessorFetchByPersonalKeyView.as_view(), name='professor-fetch-by-key'),
]