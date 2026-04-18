from collections import OrderedDict

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView

from institute_api.permissions import InstituteKeyPermission

from .models import ActivityEvent
from .pagination import ActivityTimelinePagination
from .serializers import ActivityEventSerializer


TRUE_QUERY_VALUES = {'1', 'true', 'yes', 'all'}


class ActivityTimelineView(GenericAPIView):
    permission_classes = [InstituteKeyPermission]
    serializer_class = ActivityEventSerializer
    pagination_class = ActivityTimelinePagination

    def _should_return_all(self):
        raw_all = (self.request.query_params.get('all') or '').strip().lower()
        raw_date = (self.request.query_params.get('date') or '').strip().lower()
        return raw_all in TRUE_QUERY_VALUES or raw_date == 'all'

    def _resolve_selected_date(self):
        raw_date = (self.request.query_params.get('date') or '').strip()
        if not raw_date:
            return timezone.localdate()

        selected_date = parse_date(raw_date)
        if selected_date is None:
            raise ValidationError({'date': ['Enter a valid date in YYYY-MM-DD format.']})
        return selected_date

    def get(self, request):
        institute = request._verified_institute
        return_all = self._should_return_all()
        queryset = (
            ActivityEvent.objects
            .filter(institute=institute)
            .order_by('-occurred_at', '-id')
        )

        selected_date = None
        if not return_all:
            selected_date = self._resolve_selected_date()
            queryset = queryset.filter(occurred_at__date=selected_date)

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        latest_id = page[0].id if page else 0
        return self.get_paginated_response(OrderedDict([
            ('id', institute.id),
            ('name', institute.name),
            ('scope', 'all' if return_all else 'date'),
            ('date', 'all' if return_all else selected_date.isoformat()),
            ('timeline', serializer.data),
            ('latest_id', latest_id),
        ]))
