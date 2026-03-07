from django.urls import path
from . import  views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
urlpatterns = [
    path('sign_up/', views.RegisterUserView.as_view(), name='auth_register'),
    path('login/', views.EmailLoginView.as_view(), name='login'),
    path('logout/', views.UserLogOutView.as_view(), name='logout'),
]