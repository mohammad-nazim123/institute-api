import re

from django.utils import timezone
from rest_framework import serializers

from .models import DefaultActivity


SESSION_YEAR_LIMIT = 10
SESSION_YEAR_PATTERN = re.compile(r'^(\d{4})-(\d{4})$')

MONTH_LABELS = {
    'jan': 'Jan',
    'feb': 'Feb',
    'mar': 'Mar',
    'apr': 'Apr',
    'may': 'May',
    'jun': 'Jun',
    'jul': 'Jul',
    'aug': 'Aug',
    'sep': 'Sep',
    'oct': 'Oct',
    'nov': 'Nov',
    'dec': 'Dec',
}

TIME_INPUT_FORMATS = (
    '%I:%M %p',
    '%I:%M%p',
    '%H:%M',
    '%H:%M:%S',
)


def normalize_session_month(value):
    parts = str(value or '').strip().split('-')
    if len(parts) != 2:
        raise serializers.ValidationError(
            'session_month must use month range format like Jan-Dec.'
        )

    normalized = []
    for part in parts:
        month = MONTH_LABELS.get(part.strip().lower())
        if month is None:
            raise serializers.ValidationError(
                'session_month must use valid 3-letter month names like Jan-Dec.'
            )
        normalized.append(month)

    return '-'.join(normalized)


def normalize_session_year(value):
    raw_value = str(value or '').strip()
    match = SESSION_YEAR_PATTERN.match(raw_value)
    if match is None:
        raise serializers.ValidationError(
            'session_year must use year range format like 2026-2027.'
        )

    start_year = int(match.group(1))
    end_year = int(match.group(2))
    if end_year != start_year + 1:
        raise serializers.ValidationError(
            'session_year must be a consecutive academic year range like 2026-2027.'
        )

    current_year = timezone.localdate().year
    if start_year < current_year or start_year >= current_year + SESSION_YEAR_LIMIT:
        raise serializers.ValidationError(
            'session_year must be one of the next 10 academic session years.'
        )

    return f'{start_year}-{end_year}'


class DefaultActivitySerializer(serializers.ModelSerializer):
    institute_name = serializers.CharField(source='institute.name', read_only=True)
    session_month = serializers.CharField(required=False)
    session_year = serializers.CharField(required=False)
    opening_time = serializers.TimeField(
        format='%I:%M %p',
        input_formats=TIME_INPUT_FORMATS,
        required=False,
    )
    closing_time = serializers.TimeField(
        format='%I:%M %p',
        input_formats=TIME_INPUT_FORMATS,
        required=False,
    )
    total_yearly_leaves = serializers.IntegerField(min_value=0, required=False)

    class Meta:
        model = DefaultActivity
        fields = [
            'id',
            'institute',
            'institute_name',
            'session_month',
            'session_year',
            'opening_time',
            'closing_time',
            'total_yearly_leaves',
            'created_at',
            'updated_at',
        ]
        read_only_fields = (
            'id',
            'institute',
            'institute_name',
            'created_at',
            'updated_at',
        )
        validators = []

    def validate_session_month(self, value):
        return normalize_session_month(value)

    def validate_session_year(self, value):
        return normalize_session_year(value)

    def validate(self, attrs):
        institute = self.context['institute']
        request = self.context.get('request')

        if request is not None and hasattr(request, 'data'):
            request_institute = request.data.get('institute')
            if (
                request_institute not in (None, '')
                and str(request_institute) != str(institute.id)
            ):
                raise serializers.ValidationError({
                    'institute': ['Institute does not match the authenticated institute.'],
                })

        queryset = DefaultActivity.objects.filter(institute=institute)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                'Default activity already exists for this institute.'
            )

        opening_time = attrs.get('opening_time', getattr(self.instance, 'opening_time', None))
        closing_time = attrs.get('closing_time', getattr(self.instance, 'closing_time', None))
        if (
            opening_time is not None
            and closing_time is not None
            and closing_time <= opening_time
        ):
            raise serializers.ValidationError(
                {'closing_time': ['closing_time must be later than opening_time.']}
            )

        return attrs

    def create(self, validated_data):
        validated_data['institute'] = self.context['institute']
        return super().create(validated_data)
