import re

from institute_api.permissions import FULL_ACCESS_CONTROL, normalize_access_control

from .models import ActivityEvent


ACTION_VERBS = {
    'create': 'created',
    'update': 'updated',
    'delete': 'deleted',
    'mark': 'recorded',
    'publish': 'published',
    'sync': 'synced',
    'archive': 'archived',
    'activate': 'activated',
    'deactivate': 'deactivated',
    'review': 'reviewed',
    'request': 'requested',
}


def prettify_label(value):
    normalized = re.sub(r'[_-]+', ' ', str(value or '').strip())
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.title() if normalized else 'Record'


def resolve_activity_actor(request):
    subordinate = getattr(request, '_verified_subordinate_access', None)
    if subordinate is not None:
        return {
            'actor_name': getattr(request, '_verified_actor_name', '') or getattr(subordinate, 'name', ''),
            'actor_role': getattr(request, '_verified_actor_role', '') or getattr(subordinate, 'post', 'Subordinate'),
            'actor_access_control': normalize_access_control(getattr(subordinate, 'access_control', '')),
            'actor_source': 'subordinate_access',
        }

    professor = getattr(request, '_verified_professor', None)
    if professor is not None:
        return {
            'actor_name': getattr(professor, 'name', ''),
            'actor_role': 'Professor',
            'actor_access_control': 'personal key',
            'actor_source': 'professor_personal_key',
        }

    student = getattr(request, '_verified_student', None)
    if student is not None:
        return {
            'actor_name': getattr(student, 'name', ''),
            'actor_role': 'Student',
            'actor_access_control': 'personal key',
            'actor_source': 'student_personal_key',
        }

    institute = getattr(request, '_verified_institute', None)
    return {
        'actor_name': getattr(request, '_verified_actor_name', '') or getattr(institute, 'super_admin_name', ''),
        'actor_role': getattr(request, '_verified_actor_role', '') or 'Super Admin',
        'actor_access_control': normalize_access_control(getattr(request, '_verified_access_control', '')) or FULL_ACCESS_CONTROL,
        'actor_source': 'super_admin',
    }


def build_activity_title(actor_snapshot, action, entity_type):
    actor_role = actor_snapshot.get('actor_role') or 'Team Member'
    verb = ACTION_VERBS.get(action, prettify_label(action).lower())
    entity_label = prettify_label(entity_type).lower()
    return f'{actor_role} {verb} {entity_label}'


def build_activity_description(action, entity_name='', fallback=''):
    cleaned_name = str(entity_name or '').strip()
    if fallback:
        return fallback
    if not cleaned_name:
        return ''
    verb = ACTION_VERBS.get(action, prettify_label(action).lower())
    return f'{cleaned_name} was {verb}.'


def log_activity(
    request,
    *,
    institute=None,
    action,
    entity_type,
    entity_id=None,
    entity_name='',
    title=None,
    description='',
    details=None,
    occurred_at=None,
):
    resolved_institute = institute or getattr(request, '_verified_institute', None)
    if resolved_institute is None:
        return None

    actor_snapshot = resolve_activity_actor(request)
    create_kwargs = {
        'institute': resolved_institute,
        'actor_name': actor_snapshot['actor_name'],
        'actor_role': actor_snapshot['actor_role'],
        'actor_access_control': actor_snapshot['actor_access_control'],
        'actor_source': actor_snapshot['actor_source'],
        'action': str(action),
        'entity_type': str(entity_type),
        'entity_id': entity_id,
        'entity_name': str(entity_name or ''),
        'title': title or build_activity_title(actor_snapshot, action, entity_type),
        'description': build_activity_description(action, entity_name, fallback=description),
        'details': details or {},
    }
    if occurred_at is not None:
        create_kwargs['occurred_at'] = occurred_at

    return ActivityEvent.objects.create(
        **create_kwargs,
    )


class ActivityLogMixin:
    activity_entity_type = ''
    activity_name_field = 'name'

    def get_activity_entity_type(self, action, instance):
        return self.activity_entity_type or instance.__class__.__name__

    def get_activity_entity_name(self, instance):
        field_path = getattr(self, 'activity_name_field', '')
        if callable(field_path):
            return str(field_path(instance) or '')

        current = instance
        for part in str(field_path or '').split('.'):
            if not part:
                continue
            current = getattr(current, part, None)
            if current is None:
                return ''
        return str(current or '')

    def get_activity_details(self, action, instance):
        request = getattr(self, 'request', None)
        data = getattr(request, 'data', None)
        if not hasattr(data, 'keys'):
            return {}

        fields = [
            str(key)
            for key in data.keys()
            if str(key) != 'institute'
        ]
        if not fields:
            return {}
        return {'fields': sorted(set(fields))}

    def get_activity_description(self, action, instance):
        return ''

    def get_activity_title(self, action, instance):
        return None

    def log_instance_activity(self, action, instance, *, payload=None):
        payload = dict(payload or {})
        entity_id = payload.pop('entity_id', getattr(instance, 'pk', None))
        entity_name = payload.pop('entity_name', self.get_activity_entity_name(instance))
        description = payload.pop('description', self.get_activity_description(action, instance))
        title = payload.pop('title', self.get_activity_title(action, instance))
        details = payload.pop('details', self.get_activity_details(action, instance))

        return log_activity(
            self.request,
            institute=getattr(self.request, '_verified_institute', None),
            action=action,
            entity_type=self.get_activity_entity_type(action, instance),
            entity_id=entity_id,
            entity_name=entity_name,
            title=title,
            description=description,
            details=details,
            occurred_at=payload.pop('occurred_at', None),
        )

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self.log_instance_activity('create', serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self.log_instance_activity('update', serializer.instance)

    def perform_destroy(self, instance):
        payload = {
            'entity_id': getattr(instance, 'pk', None),
            'entity_name': self.get_activity_entity_name(instance),
            'description': self.get_activity_description('delete', instance),
            'title': self.get_activity_title('delete', instance),
            'details': self.get_activity_details('delete', instance),
        }
        super().perform_destroy(instance)
        self.log_instance_activity('delete', instance, payload=payload)
