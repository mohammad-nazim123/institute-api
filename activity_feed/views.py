from collections import OrderedDict

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView

from institute_api.permissions import InstituteKeyPermission

from .models import ActivityEvent
from .pagination import ActivityTimelinePagination
from .serializers import ActivityEventSerializer


class ActivityTimelineView(GenericAPIView):
    permission_classes = [InstituteKeyPermission]
    serializer_class = ActivityEventSerializer
    pagination_class = ActivityTimelinePagination

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
        selected_date = self._resolve_selected_date()
        queryset = (
            ActivityEvent.objects
            .filter(
                institute=institute,
                occurred_at__date=selected_date,
            )
            .order_by('-occurred_at', '-id')
        )
        latest_id = queryset.values_list('id', flat=True).first() or 0

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(OrderedDict([
            ('id', institute.id),
            ('name', institute.name),
            ('date', selected_date.isoformat()),
            ('timeline', serializer.data),
            ('latest_id', latest_id),
        ]))
