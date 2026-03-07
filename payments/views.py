from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from institute_api.mixins import InstituteDictResponseMixin
from institute_api.permissions import AttendancePermission
from .models import ProfessorsPayments
from .serializers import ProfessorsPaymentsSerializer


class ProfessorsPaymentsViewSet(InstituteDictResponseMixin, ModelViewSet):
    """
    Standard CRUD for professor payments.
    All endpoints require ?institute=<id>&admin_key=<key>
    """
    serializer_class = ProfessorsPaymentsSerializer
    entity_key = 'professors_payments'
    permission_classes = [AttendancePermission]

    def get_queryset(self):
        return ProfessorsPayments.objects.select_related(
            'institute', 'professor'
        ).all()


class ProfessorPaymentUpsertView(APIView):
    """
    POST /admin_payments/upsert/
    Create OR update a professor's payment for a given month.

    Body:
    {
        "institute": 1,
        "professor": 5,
        "month_year": "2025-02",       // YYYY-MM format
        "payment_date": "2025-02-28",  // optional, actual date paid
        "payment_amount": 45000,
        "payment_status": "paid"       // e.g. "paid", "pending", "partial"
    }
    Returns the created/updated payment record wrapped in institute dict.
    """
    permission_classes = [AttendancePermission]

    def post(self, request):
        institute = getattr(request, '_verified_institute', None)
        professor_id = request.data.get('professor')
        month_year = request.data.get('month_year')

        if not professor_id or not month_year:
            return Response(
                {'detail': 'professor and month_year are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Upsert: get existing or prepare new
        try:
            existing = ProfessorsPayments.objects.get(
                professor_id=professor_id,
                month_year=month_year
            )
            serializer = ProfessorsPaymentsSerializer(
                existing, data=request.data, partial=True
            )
        except ProfessorsPayments.DoesNotExist:
            serializer = ProfessorsPaymentsSerializer(data=request.data)

        if serializer.is_valid():
            payment = serializer.save()
            return Response(
                ProfessorsPaymentsSerializer(payment).data,
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
