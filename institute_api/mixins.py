from rest_framework.response import Response
from collections import OrderedDict
from institute_api.permissions import InstituteKeyPermission
from rest_framework import serializers


class InstituteDictResponseMixin:
    """
    Mixin that:
    1. Enforces admin_key auth — every request must include the correct key for the institute.
    2. Reformats responses into a nested institute dictionary.

    ViewSets using this mixin should define:
        - institute_field: ForeignKey field name to Institute (default: 'institute')
        - entity_key: key name in the response dict (e.g., 'students')
    """
    institute_field = 'institute'
    entity_key = None  # Must be set by subclass, e.g., 'students'
    entity_name_field = 'name'
    permission_classes = [InstituteKeyPermission]


    def _build_institute_list(self, serialized_data, many=True):
        """
        Convert a flat list of serialized entities into a nested list:
        [
            {
                "id": 1,
                "name": "Institute Name",
                "<entity_key>": [ ...entity data... ]
            }
        ]
        """
        institutes = OrderedDict()

        if not many:
            serialized_data = [serialized_data]

        institute_map = self._get_institute_map(serialized_data)

        for item in serialized_data:
            institute_id, institute_name = self._get_institute_info(
                item,
                institute_map=institute_map,
            )

            if institute_id not in institutes:
                institutes[institute_id] = OrderedDict([
                    ('id', institute_id),
                    ('name', institute_name),
                    ('students', []),
                    ('professors', []),
                    ('courses', []),
                    ('weekly_schedules', []),
                    ('exam_schedules', []),
                    ('professors_payments', []),
                ])

            institutes[institute_id][self.entity_key].append(item)

        return list(institutes.values())

    def _get_institute_map(self, serialized_data):
        institute_ids = set()

        for item in serialized_data:
            institute_val = item.get(self.institute_field)
            if isinstance(institute_val, dict) or institute_val is None:
                continue
            institute_ids.add(institute_val)

        if not institute_ids:
            return {}

        from iinstitutes_list.models import Institute

        return {
            institute.id: institute.name
            for institute in Institute.objects.filter(pk__in=institute_ids).only('id', 'name')
        }

    def _get_institute_info(self, item, institute_map=None):
        """Get institute id and name from serialized data."""
        institute_val = item.get(self.institute_field)
        if isinstance(institute_val, dict):
            return institute_val.get('id'), institute_val.get('name', 'Unknown Institute')
        
        if institute_val is not None:
            if institute_map and institute_val in institute_map:
                return institute_val, institute_map[institute_val]
            return institute_val, 'Unknown Institute'
        return None, 'Unassigned'

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Filter by institute if provided
        institute_id = request.query_params.get('institute')
        if institute_id:
            queryset = queryset.filter(**{self.institute_field: institute_id})

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            result = self._build_institute_list(serializer.data, many=True)
            return self.get_paginated_response(result)

        serializer = self.get_serializer(queryset, many=True)
        result = self._build_institute_list(serializer.data, many=True)
        return Response(result)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        result = self._build_institute_list(serializer.data, many=False)
        return Response(result[0] if result else {})

    def create(self, request, *args, **kwargs):
        if hasattr(super(), 'create'):
            response = super().create(request, *args, **kwargs)
            result = self._build_institute_list(response.data, many=False)
            response.data = result[0] if result else {}
            return response
        return Response({})

    def update(self, request, *args, **kwargs):
        if hasattr(super(), 'update'):
            response = super().update(request, *args, **kwargs)
            result = self._build_institute_list(response.data, many=False)
            response.data = result[0] if result else {}
            return response
        return Response({})

    def partial_update(self, request, *args, **kwargs):
        if hasattr(super(), 'update'):
            kwargs['partial'] = True
            response = super().update(request, *args, **kwargs)
            result = self._build_institute_list(response.data, many=False)
            response.data = result[0] if result else {}
            return response
        return Response({})

class OptionalAndBlankMixin:
    """
    Mixin to make all fields optional and allow blanks, except 'name'.
    Also converts empty strings to omitted fields for non-string fields to avoid validation errors,
    effectively allowing the model default to be applied.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'name':
                field.required = True
                if hasattr(field, 'allow_blank'):
                    field.allow_blank = False
            else:
                field.required = False
                if hasattr(field, 'allow_blank'):
                    field.allow_blank = True
                if hasattr(field, 'allow_null'):
                    field.allow_null = True

    def to_internal_value(self, data):
        # DRF data might be an immutable QueryDict or dict
        if hasattr(data, '_mutable') and not getattr(data, '_mutable', True):
            mutable_data = data.copy()
        elif isinstance(data, dict):
            mutable_data = dict(data)
        else:
            mutable_data = data

        if isinstance(mutable_data, dict) or hasattr(mutable_data, '__setitem__'):
            for key, value in list(mutable_data.items()):
                if value == "":
                    field = self.fields.get(key)
                    if field and not isinstance(field, serializers.CharField):
                        # Convert empty string to None so non-string fields don't run type validation on ""
                        mutable_data[key] = None
                        
        return super().to_internal_value(mutable_data)
