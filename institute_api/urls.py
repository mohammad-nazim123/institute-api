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
from django.urls import path, include, re_path
from . import views

urlpatterns = [
    re_path(r'^ping/?$', views.ping, name='ping'),
    path('admin/', admin.site.urls),
    path('admin_students/', include('students.urls')),
    path('auth/', include('my_auth.urls')),
    path('institutes/', include('iinstitutes_list.urls')),
    path('syllabus/', include('syllabus.urls')),
    path('professors/', include('professors.urls')),
    path('admin_payments/', include('payments.urls')),
    path('attendance/', include('attendance.urls')),
    path('professor_attendance/', include('professor_attendance.urls')),
    path('super_admin_account_details/', include('super_admin_account_details.urls')),
    path('employee_account_details/', include('employee_account_details.urls')),
    path('payment_notifications/', include('payment_notification.urls')),
    path('data_analysis/', include('data_analysis.urls')),
    path('notifications/', include('notifications.urls')),
    path('exam/', include('set_exam_data.urls')),
    path('weekly_exam_schedule/', include('weekly_exam_schedule.urls')),
    path('published_students/', include('published_student.urls')),
    path('published_professors/', include('published_professors.urls')),
    path('professor_leaves/', include('professor_leaves.urls')),
    path('subordinate_access/', include('subordinate_access.urls')),
    path('activity_feed/', include('activity_feed.urls')),
    path('default_activities/', include('default_activities.urls')),
    path('contact_us/', include('contact_us.urls')),
]
