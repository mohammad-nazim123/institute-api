from calendar import isleap, monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db.models import Q
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from activity_feed.services import ActivityLogMixin
from default_activities.models import DefaultActivity
from professor_leaves.models import ProfessorLeave

from .models import PaymentNotification
from .permissions import InstitutePaymentNotificationPermission
from .serializers import PaymentNotificationSerializer


TWOPLACES = Decimal('0.01')


def get_payment_notification_queryset(request):
    return PaymentNotification.objects.select_related(
        'professor',
        'professor__experience',
        'professor__admin_employement',
    ).filter(
        institute=request._verified_institute
    ).order_by('-payment_month_key', 'id')


def apply_payment_notification_filters(queryset, request):
    professor_id = (request.query_params.get('professor') or '').strip()
    if professor_id:
        queryset = queryset.filter(professor_id=professor_id)

    payment_month = (request.query_params.get('payment_month') or '').strip()
    if payment_month:
        queryset = queryset.filter(payment_month_key=payment_month)

    status = (request.query_params.get('status') or '').strip().lower()
    if status and status != 'all':
        allowed_statuses = {choice for choice, _ in PaymentNotification.Status.choices}
        if status not in allowed_statuses:
            raise ValidationError(
                {'status': ['status must be one of pending, approved, rejected, or all.']}
            )
        queryset = queryset.filter(status=status)

    search = (request.query_params.get('search') or '').strip()
    if search:
        queryset = queryset.filter(
            Q(professor__name__icontains=search)
            | Q(professor__experience__department__icontains=search)
            | Q(professor__admin_employement__employee_id__icontains=search)
        )

    return queryset


def parse_payment_month_value(value):
    raw_value = str(value or '').strip()
    if len(raw_value) != 7 or raw_value[4] != '-':
        return None

    try:
        year = int(raw_value[:4])
        month = int(raw_value[5:7])
    except (TypeError, ValueError):
        return None

    if month < 1 or month > 12:
        return None

    return year, month


def add_one_month(value):
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def iter_month_starts(start_date, end_date):
    current = date(start_date.year, start_date.month, 1)

    while current <= end_date:
        yield current
        current = add_one_month(current)


def safe_decimal(value, default='0.00'):
    try:
        return Decimal(str(value if value not in (None, '') else default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def format_currency_value(value):
    return format(safe_decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP), 'f')


def get_related_or_none(instance, relation_name):
    try:
        return getattr(instance, relation_name)
    except Exception:
        return None


def get_days_in_year(year):
    return 366 if isleap(year) else 365


def build_professor_year_maps(notifications):
    professor_years = defaultdict(set)

    for notification in notifications:
        parsed_payment_month = parse_payment_month_value(
            notification.payment_month_key or notification.payment_month
        )
        if parsed_payment_month is None:
            continue
        year, _ = parsed_payment_month
        professor_years[notification.professor_id].add(year)

    return professor_years


def build_leave_summary_maps(accepted_leaves, professor_years):
    monthly_totals = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for leave in accepted_leaves:
        professor_id = getattr(leave.published_professor, 'source_professor_id', None)
        relevant_years = professor_years.get(professor_id)
        if not professor_id or not relevant_years:
            continue

        start_bound = date(min(relevant_years), 1, 1)
        end_bound = date(max(relevant_years), 12, 31)
        overlap_start = max(leave.start_date, start_bound)
        overlap_end = min(leave.end_date, end_bound)

        if overlap_end < overlap_start:
            continue

        for month_start in iter_month_starts(overlap_start, overlap_end):
            year = month_start.year
            month = month_start.month

            if year not in relevant_years:
                continue

            month_end = date(year, month, monthrange(year, month)[1])
            chunk_start = max(overlap_start, month_start)
            chunk_end = min(overlap_end, month_end)

            if chunk_end < chunk_start:
                continue

            monthly_totals[professor_id][year][month] += (
                chunk_end - chunk_start
            ).days + 1

    prefix_totals = defaultdict(dict)
    normalized_monthly_totals = defaultdict(dict)

    for professor_id, years in monthly_totals.items():
        for year, months in years.items():
            running_total = 0
            prefix_values = [0] * 13
            normalized_months = {}

            for month in range(1, 13):
                month_total = int(months.get(month, 0))
                normalized_months[month] = month_total
                running_total += month_total
                prefix_values[month] = running_total

            normalized_monthly_totals[professor_id][year] = normalized_months
            prefix_totals[professor_id][year] = prefix_values

    return normalized_monthly_totals, prefix_totals


def serialize_summary_row(
    notification,
    institute_total_leaves,
    monthly_totals,
    prefix_totals,
):
    professor = notification.professor
    employee_record = get_related_or_none(professor, 'admin_employement')
    experience_record = get_related_or_none(professor, 'experience')
    payment_month_value = notification.payment_month_key or notification.payment_month
    parsed_payment_month = parse_payment_month_value(payment_month_value)

    payment_month_leaves = 0
    accepted_leaves_till_month = 0
    remaining_leaves = None
    extra_leaves_this_month = 0
    amount_per_day = Decimal('0.00')

    if parsed_payment_month is not None:
        year, month = parsed_payment_month
        professor_month_totals = monthly_totals.get(notification.professor_id, {}).get(year, {})
        professor_prefix_totals = prefix_totals.get(notification.professor_id, {}).get(year, [0] * 13)
        payment_month_leaves = int(professor_month_totals.get(month, 0))
        accepted_leaves_till_month = int(professor_prefix_totals[month])

        if institute_total_leaves is not None:
            accepted_before_month = int(professor_prefix_totals[month - 1]) if month > 1 else 0
            remaining_leaves = max(int(institute_total_leaves) - accepted_leaves_till_month, 0)
            extra_leaves_this_month = max(
                accepted_leaves_till_month - int(institute_total_leaves),
                0,
            ) - max(
                accepted_before_month - int(institute_total_leaves),
                0,
            )

        gross_amount = safe_decimal(notification.gross_amount or notification.final_amount)
        days_in_year = get_days_in_year(year)
        if days_in_year > 0:
            amount_per_day = (
                (gross_amount * Decimal('12')) / Decimal(days_in_year)
            ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    return {
        'id': notification.id,
        'institute': notification.institute_id,
        'professor': notification.professor_id,
        'professor_name': professor.name,
        'department': getattr(experience_record, 'department', None),
        'employee_id': getattr(employee_record, 'employee_id', ''),
        'account_holder_name': notification.account_holder_name,
        'bank_name': notification.bank_name,
        'account_number': notification.account_number,
        'ifsc_code': notification.ifsc_code,
        'gross_amount': format_currency_value(notification.gross_amount or notification.final_amount),
        'deducted_amount': format_currency_value(notification.deducted_amount),
        'final_amount': format_currency_value(notification.final_amount),
        'payment_month': notification.payment_month,
        'payment_date': notification.payment_date,
        'approved_leaves': int(notification.approved_leaves or 0),
        'status': notification.status,
        'payment_month_leaves': payment_month_leaves,
        'accepted_leaves_till_month': accepted_leaves_till_month,
        'remaining_leaves': remaining_leaves,
        'extra_leaves_this_month': extra_leaves_this_month,
        'amount_per_day': format(amount_per_day, 'f'),
        'created_at': notification.created_at.isoformat() if notification.created_at else None,
        'updated_at': notification.updated_at.isoformat() if notification.updated_at else None,
    }


class PaymentNotificationListCreateView(ActivityLogMixin, generics.ListCreateAPIView):
    activity_entity_type = 'payment request'
    activity_name_field = 'payment_month_key'
    permission_classes = [InstitutePaymentNotificationPermission]
    serializer_class = PaymentNotificationSerializer

    def get_queryset(self):
        return apply_payment_notification_filters(
            get_payment_notification_queryset(self.request),
            self.request,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class PaymentNotificationDetailView(ActivityLogMixin, generics.RetrieveUpdateDestroyAPIView):
    activity_entity_type = 'payment request'
    activity_name_field = 'payment_month_key'
    permission_classes = [InstitutePaymentNotificationPermission]
    serializer_class = PaymentNotificationSerializer

    def get_queryset(self):
        return get_payment_notification_queryset(self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class PaymentNotificationSummaryView(generics.GenericAPIView):
    permission_classes = [InstitutePaymentNotificationPermission]

    def get(self, request, *args, **kwargs):
        institute = request._verified_institute
        base_queryset = get_payment_notification_queryset(request)
        filtered_queryset = apply_payment_notification_filters(base_queryset, request)
        notifications = list(filtered_queryset)

        total_count = base_queryset.count()
        institute_default_activity = DefaultActivity.objects.filter(
            institute=institute,
        ).only(
            'total_yearly_leaves',
        ).first()
        institute_total_leaves = (
            institute_default_activity.total_yearly_leaves
            if institute_default_activity is not None
            else None
        )

        professor_years = build_professor_year_maps(notifications)
        accepted_leaves = []

        if professor_years:
            relevant_professor_ids = sorted(professor_years.keys())
            relevant_years = sorted(
                {
                    year
                    for years in professor_years.values()
                    for year in years
                }
            )
            accepted_leaves = list(
                ProfessorLeave.objects.select_related('published_professor').filter(
                    institute=institute,
                    leaves_status=ProfessorLeave.LeaveStatus.ACCEPTED,
                    published_professor__source_professor_id__in=relevant_professor_ids,
                    start_date__lte=date(max(relevant_years), 12, 31),
                    end_date__gte=date(min(relevant_years), 1, 1),
                )
            )

        monthly_totals, prefix_totals = build_leave_summary_maps(
            accepted_leaves,
            professor_years,
        )

        return Response(
            {
                'total_count': total_count,
                'count': len(notifications),
                'institute_total_leaves': institute_total_leaves,
                'results': [
                    serialize_summary_row(
                        notification,
                        institute_total_leaves,
                        monthly_totals,
                        prefix_totals,
                    )
                    for notification in notifications
                ],
            }
        )
