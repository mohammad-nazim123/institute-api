from django.urls import path

from . import views


urlpatterns = [
    path('', views.PublishedProfessorListView.as_view(), name='published-professor-list'),
    path('lookup-id/', views.PublishedProfessorIdLookupView.as_view(), name='published-professor-lookup-id'),
    path('<int:professor_id>/', views.PublishedProfessorDetailView.as_view(), name='published-professor-detail'),
]
