from django.urls import path

from .views import ArchiveDetailView, ArchiveListCreateView


urlpatterns = [
    path('', ArchiveListCreateView.as_view(), name='archives-list-create'),
    path('<int:pk>/', ArchiveDetailView.as_view(), name='archives-detail'),
]
