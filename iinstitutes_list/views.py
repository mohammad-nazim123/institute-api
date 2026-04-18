from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Prefetch
from .models import Institute
from .serializers import (
    InstituteSerializer,
    InstituteDetailSerializer,
    InstituteSummarySerializer,
    InstituteVerifySerializer,
)
from professors.models import Professor
from students.models import Student
from syllabus.models import AcademicTerms, Branch, Course, Subject
from subordinate_access.models import SubordinateAccess


def get_institute_detail_queryset():
    student_queryset = Student.objects.select_related(
        'contact_details',
        'education_details',
        'admission_details',
        'course_assignments',
        'fee_details',
        'system_details',
    ).order_by('id')

    professor_queryset = Professor.objects.select_related(
        'address',
        'experience',
        'admin_employement',
        'class_assigned',
    ).prefetch_related(
        'qualification',
    ).order_by('id')

    course_queryset = Course.objects.only(
        'id',
        'institute_id',
        'name',
    ).prefetch_related(
        Prefetch(
            'branches',
            queryset=Branch.objects.only(
                'id',
                'course_id',
                'name',
            ).prefetch_related(
                Prefetch(
                    'academic_terms',
                    queryset=AcademicTerms.objects.only(
                        'id',
                        'branch_id',
                        'name',
                    ).prefetch_related(
                        Prefetch(
                            'subjects',
                            queryset=Subject.objects.only(
                                'id',
                                'academic_terms_id',
                                'name',
                                'unit',
                            ),
                        )
                    ).order_by('id'),
                )
            ).order_by('id'),
        )
    ).order_by('id')

    return Institute.objects.only(
        'id',
        'institute_name',
        'super_admin_name',
        'admin_key',
        'event_status',
        'event_timer_end',
    ).prefetch_related(
        Prefetch('students', queryset=student_queryset),
        Prefetch('professors', queryset=professor_queryset),
        Prefetch('courses', queryset=course_queryset),
    )


class InstituteViewSet(ModelViewSet):
    serializer_class = InstituteSerializer

    def _uses_summary_response(self):
        return str(self.request.query_params.get('summary', '')).strip().lower() in {
            '1',
            'true',
            'yes',
        }

    def get_queryset(self):
        if self.action in ['list', 'retrieve'] and self._uses_summary_response():
            return Institute.objects.only(
                'id',
                'institute_name',
                'super_admin_name',
                'event_status',
                'event_timer_end',
            ).order_by('id')

        if self.action in ['list', 'retrieve']:
            return get_institute_detail_queryset()
        return Institute.objects.all()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve'] and self._uses_summary_response():
            return InstituteSummarySerializer

        if self.action in ['list', 'retrieve']:
            return InstituteDetailSerializer
        return InstituteSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        # Wrap the single instance in a list as requested
        return Response([serializer.data])


class InstituteVerifyView(APIView):
    """
    POST /institutes/verify/
    Accepts {"institute_name": "...", "super_admin_name": "...", "admin_key": "..."}
    Returns the institute data if the pair matches, or 403 if not.
    """

    def _subordinate_payload(self, subordinate):
        return {
            'id': subordinate.id,
            'post': subordinate.post,
            'name': subordinate.name,
            'access_control': subordinate.access_control,
            'is_active': subordinate.is_active,
        }

    def _institute_summary_payload(self, institute):
        return InstituteSummarySerializer(institute).data

    def _approved_subordinate_response(self, institute, subordinate, *, include_detail=True):
        if not include_detail:
            data = self._institute_summary_payload(institute)
            data['subordinate_access'] = self._subordinate_payload(subordinate)
            return Response(data, status=status.HTTP_200_OK)

        detail_institute = get_institute_detail_queryset().get(pk=institute.pk)
        data = InstituteDetailSerializer(detail_institute).data
        data['subordinate_access'] = self._subordinate_payload(subordinate)
        return Response(data, status=status.HTTP_200_OK)

    def _handle_subordinate_login(self, institute, admin_key, *, include_detail=True):
        subordinate = (
            SubordinateAccess.objects
            .filter(institute=institute, access_code=admin_key)
            .only('id', 'post', 'name', 'access_control', 'is_active', 'institute_id')
            .first()
        )
        if subordinate is None:
            return Response(
                {'detail': 'Invalid institute name or admin key.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if subordinate.is_active:
            return self._approved_subordinate_response(
                institute,
                subordinate,
                include_detail=include_detail,
            )

        return Response(
            {
                'detail': 'This access key is deactive right now. Please contact the Super Admin.',
                'subordinate_access': self._subordinate_payload(subordinate),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    def post(self, request):
        serializer = InstituteVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        institute_name = serializer.validated_data['institute_name']
        super_admin_name = serializer.validated_data.get('super_admin_name', '')
        admin_key = serializer.validated_data['admin_key']
        include_detail = serializer.validated_data.get('include_detail', True)

        if len(admin_key) == 32:
            try:
                institute = Institute.objects.only(
                    'id',
                    'institute_name',
                    'super_admin_name',
                    'admin_key',
                    'event_status',
                    'event_timer_end',
                ).get(institute_name=institute_name)
            except Institute.DoesNotExist:
                return Response(
                    {'detail': 'Invalid institute name or admin key.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if institute.admin_key != admin_key:
                return Response(
                    {'detail': 'Invalid institute name or admin key.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if institute.super_admin_name != super_admin_name:
                return Response(
                    {'detail': 'Super admin name does not match.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if not include_detail:
                return Response(self._institute_summary_payload(institute))

            detail_institute = get_institute_detail_queryset().get(pk=institute.pk)
            detail_serializer = InstituteDetailSerializer(detail_institute)
            return Response(detail_serializer.data)

        try:
            institute = Institute.objects.only(
                'id',
                'institute_name',
                'super_admin_name',
                'event_status',
                'event_timer_end',
            ).get(
                institute_name=institute_name
            )
        except Institute.DoesNotExist:
            return Response(
                {'detail': 'Invalid institute name or admin key.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if len(admin_key) in {29, 30, 31}:
            return self._handle_subordinate_login(
                institute,
                admin_key,
                include_detail=include_detail,
            )

        return Response(
            {'detail': 'Invalid institute name or admin key.'},
            status=status.HTTP_403_FORBIDDEN,
        )
