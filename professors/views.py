from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from .models import Professor
from .serializers import ProfessorSerializer, ProfessorIdLookUpSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from institute_api.mixins import InstituteDictResponseMixin
from institute_api.permissions import InstituteKeyPermission, PersonalKeyPermission
from iinstitutes_list.models import Institute


class ProfessorViewSet(InstituteDictResponseMixin, ModelViewSet):
    serializer_class = ProfessorSerializer
    entity_key = 'professors'
    entity_name_field = 'name'

    def get_queryset(self):
        return Professor.objects.select_related(
            'institute',
            'address',
            'experience',
            'admin_employement',
            'class_assigned',
        ).prefetch_related(
            'qualification',
        ).all()

    def get_permissions(self):
        """retrieve uses professor's personal key; all other actions require admin key."""
        if self.action == 'retrieve':
            return [PersonalKeyPermission()]
        return [InstituteKeyPermission()]

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
            institute = Institute.objects.get(name=institute_name)
        except Institute.DoesNotExist:
            return Response(
                {'detail': 'Institute not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            professor = Professor.objects.select_related(
                'institute',
                'address',
                'experience',
                'admin_employement',
                'class_assigned',
            ).prefetch_related(
                'qualification',
            ).get(
                institute=institute,
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
    Accepts {"personal_id": "<16-digit-key>"}
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
            professor = Professor.objects.select_related(
                'institute',
                'address',
                'experience',
                'admin_employement',
                'class_assigned',
            ).prefetch_related(
                'qualification',
            ).get(admin_employement__personal_id=personal_id)
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

