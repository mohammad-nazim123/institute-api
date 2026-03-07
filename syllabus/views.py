from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from .models import Course
from .serializers import CourseSerializer
from institute_api.mixins import InstituteDictResponseMixin


class CourseViewSet(InstituteDictResponseMixin, ModelViewSet):
    serializer_class = CourseSerializer
    entity_key = 'courses'
    entity_name_field = 'name'

    def get_queryset(self):
        return Course.objects.select_related(
            'institute',
        ).prefetch_related(
            'subjects',
        ).all()
