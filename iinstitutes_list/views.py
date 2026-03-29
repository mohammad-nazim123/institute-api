from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Prefetch
from .models import Institute
from .serializers import InstituteSerializer, InstituteDetailSerializer, InstituteVerifySerializer
from professors.models import Professor
from students.models import Student
from syllabus.models import AcademicTerms, Branch, Course, Subject


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
        'name',
        'event_status',
        'event_timer_end',
    ).prefetch_related(
        Prefetch('students', queryset=student_queryset),
        Prefetch('professors', queryset=professor_queryset),
        Prefetch('courses', queryset=course_queryset),
    )


class InstituteViewSet(ModelViewSet):
    serializer_class = InstituteSerializer

    def get_queryset(self):
        if self.action in ['list', 'retrieve']:
            return get_institute_detail_queryset()
        return Institute.objects.all()

    def get_serializer_class(self):
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
    Accepts {"name": "...", "admin_key": "..."}
    Returns the institute data if the pair matches, or 403 if not.
    """

    def post(self, request):
        serializer = InstituteVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']
        admin_key = serializer.validated_data['admin_key']

        try:
            institute = get_institute_detail_queryset().get(name=name, admin_key=admin_key)
        except Institute.DoesNotExist:
            return Response(
                {'detail': 'Invalid institute name or admin key.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Return the institute data using the detail serializer
        detail_serializer = InstituteDetailSerializer(institute)
        return Response(detail_serializer.data)
