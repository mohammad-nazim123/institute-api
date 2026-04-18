from collections import OrderedDict

from activity_feed.services import ActivityLogMixin, log_activity
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from institute_api.mixins import InstituteDictResponseMixin
from institute_api.permissions import ADMIN_ACCESS_CONTROL, AttendancePermission
from .models import ProfessorsPayments
from .serializers import ProfessorsPaymentsSerializer
from professors.models import Professor


def get_payments_queryset(institute=None):
    queryset = ProfessorsPayments.objects.only(
        'id',
        'institute_id',
        'professor_id',
        'month_year',
        'payment_date',
        'payment_amount',
        'payment_status',
    ).order_by('-month_year', 'id')
    if institute is not None:
        queryset = queryset.filter(institute=institute)
    return queryset


class ProfessorsPaymentsViewSet(ActivityLogMixin, InstituteDictResponseMixin, ModelViewSet):
    activity_entity_type = 'professor payment'
    activity_name_field = 'month_year'
    """
    Standard CRUD for professor payments.
    All endpoints require ?institute=<id>&admin_key=<key>
    """
    serializer_class = ProfessorsPaymentsSerializer
    entity_key = 'professors_payments'
    permission_classes = [AttendancePermission]
    allowed_subordinate_access_controls = (ADMIN_ACCESS_CONTROL,)

    def get_queryset(self):
        return get_payments_queryset(getattr(self.request, '_verified_institute', None))

    def _build_verified_institute_response(self, institute, serialized_data):
        return OrderedDict([
            ('id', institute.id),
            ('name', institute.name),
            ('students', []),
            ('professors', []),
            ('courses', []),
            ('weekly_schedules', []),
            ('exam_schedules', []),
            ('professors_payments', serialized_data),
        ])

    def list(self, request, *args, **kwargs):
        institute = request._verified_institute
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            result = self._build_verified_institute_response(institute, serializer.data)
            return self.get_paginated_response([result])

        serializer = self.get_serializer(queryset, many=True)
        return Response([self._build_verified_institute_response(institute, serializer.data)])

    def retrieve(self, request, *args, **kwargs):
        institute = request._verified_institute
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(self._build_verified_institute_response(institute, [serializer.data]))

    def create(self, request, *args, **kwargs):
        institute = request._verified_institute
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        payment = serializer.instance
        return Response(
            self._build_verified_institute_response(
                institute,
                [self.get_serializer(payment).data],
            ),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        institute = request._verified_institute
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        payment = serializer.instance
        return Response(
            self._build_verified_institute_response(
                institute,
                [self.get_serializer(payment).data],
            )
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


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
    allowed_subordinate_access_controls = (ADMIN_ACCESS_CONTROL,)

    @staticmethod
    def _payment_payload(payment_id, institute_id, professor_id, month_year, fields):
        return {
            'id': payment_id,
            'institute': institute_id,
            'professor': professor_id,
            'month_year': month_year,
            'payment_date': fields['payment_date'],
            'payment_amount': fields['payment_amount'],
            'payment_status': fields['payment_status'],
        }

    def post(self, request):
        institute = request._verified_institute
        professor_id = request.data.get('professor')
        month_year = request.data.get('month_year')

        if not professor_id or not month_year:
            return Response(
                {'detail': 'professor and month_year are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment_fields = {
            'payment_date': None,
            'payment_amount': 0,
            'payment_status': '',
        }
        updates = {}
        for field in payment_fields:
            if field in request.data:
                updates[field] = request.data.get(field)

        if not Professor.objects.filter(pk=professor_id, institute_id=institute.id).exists():
            return Response(
                {'detail': 'Professor not found in the authenticated institute.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment, created = ProfessorsPayments.objects.update_or_create(
            institute_id=institute.id,
            professor_id=professor_id,
            month_year=month_year,
            defaults={**payment_fields, **updates} if not updates else updates,
        )

        if created:
            log_activity(
                request,
                action='create',
                entity_type='professor payment',
                entity_id=payment.id,
                entity_name=month_year,
                description=f"Professor payment for {month_year} was created.",
                details={'professor_id': professor_id, 'month_year': month_year, 'fields': sorted(updates.keys())},
            )
        elif updates:
            log_activity(
                request,
                action='update',
                entity_type='professor payment',
                entity_id=payment.id,
                entity_name=month_year,
                description=f"Professor payment for {month_year} was updated.",
                details={'professor_id': professor_id, 'month_year': month_year, 'fields': sorted(updates.keys())},
            )

        return Response(
            self._payment_payload(
                payment.id,
                institute.id,
                professor_id,
                month_year,
                {
                    'payment_date': payment.payment_date,
                    'payment_amount': payment.payment_amount,
                    'payment_status': payment.payment_status,
                },
            ),
            status=status.HTTP_200_OK,
        )
