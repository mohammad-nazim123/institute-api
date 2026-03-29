from rest_framework import generics

from .models import InstituteTotalLeave, ProfessorLeave
from .permissions import InstituteTotalLeavesPermission, ProfessorLeavesPermission
from .serializers import InstituteTotalLeaveSerializer, ProfessorLeaveSerializer


class ProfessorLeaveListCreateView(generics.ListCreateAPIView):
    permission_classes = [ProfessorLeavesPermission]
    serializer_class = ProfessorLeaveSerializer

    def get_queryset(self):
        queryset = (
            ProfessorLeave.objects
            .select_related('published_professor')
            .filter(institute=self.request._verified_institute)
            .order_by('-start_date', 'id')
        )

        verified_published_professor = getattr(self.request, '_verified_published_professor', None)
        if verified_published_professor is not None:
            queryset = queryset.filter(published_professor_id=verified_published_professor.id)

        published_professor_id = self.request.query_params.get('published_professor')
        if published_professor_id:
            queryset = queryset.filter(published_professor_id=published_professor_id)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(start_date=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(end_date=end_date)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        context['verified_published_professor'] = getattr(
            self.request,
            '_verified_published_professor',
            None,
        )
        return context


class ProfessorLeaveDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [ProfessorLeavesPermission]
    serializer_class = ProfessorLeaveSerializer

    def get_queryset(self):
        queryset = (
            ProfessorLeave.objects
            .select_related('published_professor')
            .filter(institute=self.request._verified_institute)
        )
        verified_published_professor = getattr(self.request, '_verified_published_professor', None)
        if verified_published_professor is not None:
            queryset = queryset.filter(published_professor_id=verified_published_professor.id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        context['verified_published_professor'] = getattr(
            self.request,
            '_verified_published_professor',
            None,
        )
        return context


class InstituteTotalLeaveListCreateView(generics.ListCreateAPIView):
    permission_classes = [InstituteTotalLeavesPermission]
    serializer_class = InstituteTotalLeaveSerializer

    def get_queryset(self):
        return InstituteTotalLeave.objects.filter(
            institute=self.request._verified_institute
        ).order_by('id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class InstituteTotalLeaveDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [InstituteTotalLeavesPermission]
    serializer_class = InstituteTotalLeaveSerializer

    def get_queryset(self):
        return InstituteTotalLeave.objects.filter(
            institute=self.request._verified_institute
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context
