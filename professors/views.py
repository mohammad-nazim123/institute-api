from collections import OrderedDict
from django.db.models import Prefetch
from django.db.models import Q
from rest_framework.viewsets import ModelViewSet
from .models import Professor
from .serializers import ProfessorSerializer, ProfessorIdLookUpSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from institute_api.mixins import InstituteDictResponseMixin
from institute_api.permissions import InstituteKeyPermission, PersonalKeyPermission
from .models import ProfessorQualification
from .pagination import ProfessorPagination


def get_professor_queryset(institute=None):
    queryset = Professor.objects.select_related(
        'institute',
        'address',
        'experience',
        'admin_employement',
        'class_assigned',
    ).prefetch_related(
        Prefetch(
            'qualification',
            queryset=ProfessorQualification.objects.order_by('id'),
        ),
    ).order_by('id')
    if institute is not None:
        queryset = queryset.filter(institute=institute)
    return queryset


def _clean_query_param(request, key):
    return (request.query_params.get(key) or '').strip()


class ProfessorViewSet(InstituteDictResponseMixin, ModelViewSet):
    serializer_class = ProfessorSerializer
    entity_key = 'professors'
    entity_name_field = 'name'
    pagination_class = ProfessorPagination

    def get_queryset(self):
        request = getattr(self, 'request', None)
        institute = getattr(request, '_verified_institute', None) if request is not None else None
        queryset = get_professor_queryset(institute=institute)

        if request is None:
            return queryset

        search = _clean_query_param(request, 'search')
        name = _clean_query_param(request, 'name')
        employee_id = _clean_query_param(request, 'employee_id')
        department = _clean_query_param(request, 'department')

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(admin_employement__employee_id__icontains=search)
                | Q(experience__department__icontains=search)
            )

        if name:
            queryset = queryset.filter(name__icontains=name)
        if employee_id:
            queryset = queryset.filter(admin_employement__employee_id__icontains=employee_id)
        if department:
            queryset = queryset.filter(experience__department__icontains=department)

        return queryset

    def get_permissions(self):
        """retrieve uses professor's personal key; all other actions require admin key."""
        if self.action == 'retrieve':
            return [PersonalKeyPermission()]
        return [InstituteKeyPermission()]

    def _build_verified_institute_response(self, institute, serialized_data):
        return OrderedDict([
            ('id', institute.id),
            ('name', institute.name),
            ('students', []),
            ('professors', serialized_data),
            ('courses', []),
            ('weekly_schedules', []),
            ('exam_schedules', []),
            ('professors_payments', []),
        ])

    def list(self, request, *args, **kwargs):
        institute = request._verified_institute
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            result = self._build_verified_institute_response(institute, serializer.data)
            return self.get_paginated_response(result)

        serializer = self.get_serializer(queryset, many=True)
        return Response([self._build_verified_institute_response(institute, serializer.data)])

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()          # calls has_object_permission internally
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ProfessorIdLookUpAPIView(APIView):
    def post(self, request):
        serializer = ProfessorIdLookUpSerializer(data=request.data)
        if serializer.is_valid():
            professor = serializer.instance
            return Response({
                'professor_id': professor.id,
                'status': status.HTTP_200_OK
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfessorVerifyView(APIView):
    """
    POST /professors/verify/
    Accepts {"email": "...", "personal_id": "...", "institute_name": "..."}
    Returns the full professor data if match, or error if not.
    """

    def post(self, request):
        email = request.data.get('email')
        personal_id = request.data.get('personal_id')
        institute_name = request.data.get('institute_name')

        if not email or not personal_id:
            return Response(
                {'detail': 'Both email and personal_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not institute_name:
            return Response(
                {'detail': 'institute_name is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            professor = get_professor_queryset().get(
                institute__name=institute_name,
                email=email,
                admin_employement__personal_id=personal_id
            )
        except Professor.DoesNotExist:
            return Response(
                {'detail': 'Professor not found in the selected institute.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ProfessorSerializer(professor)
        return Response(serializer.data)


class ProfessorFetchByPersonalKeyView(APIView):
    """
    POST /professors/fetch-by-key/
    Accepts {"personal_id": "<professor personal ID>"}
    Returns the professor's full data if the personal_id matches.
    Does NOT require an admin key — uses the professor's own personal key.
    """

    def post(self, request):
        personal_id = request.data.get('personal_id')

        if not personal_id:
            return Response(
                {'detail': 'personal_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            professor = get_professor_queryset().get(
                admin_employement__personal_id=personal_id,
            )
        except Professor.DoesNotExist:
            return Response(
                {'detail': 'No professor found with the given personal ID.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check that the institute is active
        if professor.institute and not professor.institute.is_event_active:
            return Response(
                {'detail': f'Institute events are currently {professor.institute.event_status}. Access denied.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ProfessorSerializer(professor)
        return Response(serializer.data)
