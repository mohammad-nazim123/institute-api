from django.urls import path

from .views import ActivityTimelineView


urlpatterns = [
    path('timeline/', ActivityTimelineView.as_view(), name='activity-timeline'),
]
