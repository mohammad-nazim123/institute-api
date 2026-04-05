from calendar import monthrange
from datetime import date

from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import InstituteTotalLeave, ProfessorLeave
from .permissions import InstituteTotalLeavesPermission, ProfessorLeavesPermission
from .serializers import InstituteTotalLeaveSerializer, ProfessorLeaveSerializer


def apply_professor_leave_month_filter(queryset, request):
    month_param = (request.query_params.get('month') or '').strip()
    year_param = (request.query_params.get('year') or '').strip()

    if not month_param:
        return queryset

    if '-' in month_param:
        try:
            year, month = month_param.split('-')
        except ValueError as exc:
            raise ValidationError(
                {'detail': 'Invalid month format. Please use YYYY-MM or pass month with year.'}
            ) from exc
    else:
        if not year_param:
            raise ValidationError(
                {'detail': 'Provide year when month is passed without YYYY-MM format.'}
            )
        year, month = year_param, month_param

    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            {'detail': 'Invalid month format. Please use YYYY-MM or pass month with year.'}
        ) from exc

    if month < 1 or month > 12:
        raise ValidationError({'detail': 'Month must be between 1 and 12.'})

    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    return queryset.filter(
        start_date__lte=month_end,
        end_date__gte=month_start,
    )


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

        professor_id = (self.request.query_params.get('professor_id') or '').strip()
        if professor_id:
            queryset = queryset.filter(
                published_professor__source_professor_id=professor_id
            )

        leaves_status = (
            (self.request.query_params.get('leaves_status') or '').strip()
            or (self.request.query_params.get('status') or '').strip()
        )
        if leaves_status:
            queryset = queryset.filter(leaves_status=leaves_status)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(start_date=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(end_date=end_date)

        return apply_professor_leave_month_filter(queryset, self.request)

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
