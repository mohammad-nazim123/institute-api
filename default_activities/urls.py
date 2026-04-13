from django.urls import path

from .views import (
    AcademicTermDetailView,
    AcademicTermListCreateView,
    DefaultActivityDetailView,
    DefaultActivityListCreateView,
)


urlpatterns = [
    path('', DefaultActivityListCreateView.as_view(), name='default-activity-list-create'),
    path('<int:pk>/', DefaultActivityDetailView.as_view(), name='default-activity-detail'),
    path('academic-terms/', AcademicTermListCreateView.as_view(), name='academic-term-list-create'),
    path('academic-terms/<int:pk>/', AcademicTermDetailView.as_view(), name='academic-term-detail'),
]
