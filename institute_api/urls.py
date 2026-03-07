"""
URL configuration for institute_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin_students/', include('students.urls')),
    path('auth/', include('my_auth.urls')),
    path('institutes/', include('iinstitutes_list.urls')),
    path('syllabus/', include('syllabus.urls')),
    path('professors/', include('professors.urls')),
    path('schedules/', include('schedules.urls')),
    path('unique-ids/', include('unique_ids.urls')),
    path('admin_payments/', include('payments.urls')),
    path('attendance/', include('attendance.urls')),
]

