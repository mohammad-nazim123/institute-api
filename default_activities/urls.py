from django.urls import path

from .views import DefaultActivityDetailView, DefaultActivityListCreateView


urlpatterns = [
    path('', DefaultActivityListCreateView.as_view(), name='default-activity-list-create'),
    path('<int:pk>/', DefaultActivityDetailView.as_view(), name='default-activity-detail'),
]
