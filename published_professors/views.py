from collections import OrderedDict

from activity_feed.services import log_activity

from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from professors.models import Professor, ProfessorQualification
from professors.serializers import ProfessorSerializer

from .models import PublishedProfessor
from .permissions import (
    PublishedProfessorAdminKeyPermission,
    PublishedProfessorPersonalKeyPermission,
)
from .serializers import (
    PublishedProfessorIdLookupSerializer,
    PublishedProfessorSerializer,
)


ALREADY_EXISTS_MESSAGE = 'The data already exist.'
SINGLE_ALREADY_EXISTS_MESSAGE = 'This professor is already available.'

PUBLISHED_ONLY_FIELDS = (
    'id',
    'institute_id',
    'source_professor_id',
    'name',
    'email',
    'professor_personal_id',
    'professor_data',
    'published_at',
    'updated_at',
)


def get_professor_publish_queryset(institute, professor_id=None):
    queryset = (
        Professor.objects
        .filter(institute=institute)
        .select_related(
            'institute',
            'address',
            'experience',
            'admin_employement',
            'class_assigned',
        )
        .prefetch_related(
            Prefetch(
                'qualification',
                queryset=ProfessorQualification.objects.order_by('id'),
            )
        )
        .order_by('id')
    )
    if professor_id is not None:
        queryset = queryset.filter(id=professor_id)
    return queryset


def get_published_professor_queryset(institute):
    return (
        PublishedProfessor.objects
        .filter(institute=institute)
        .only(*PUBLISHED_ONLY_FIELDS)
        .order_by('source_professor_id')
    )


def get_published_professor_lookup_queryset(institute):
    return (
        PublishedProfessor.objects
        .filter(institute=institute)
        .only('id', 'institute_id', 'source_professor_id', 'email', 'professor_personal_id')
        .order_by('source_professor_id')
    )


def build_professor_snapshot(professor):
    return ProfessorSerializer(professor).data


def get_professor_personal_id(professor_data):
    admin_employement = professor_data.get('admin_employement') or {}
    return admin_employement.get('personal_id', '')


def snapshot_has_changed(existing, professor_name, professor_email, professor_personal_id, professor_data):
    return any([
        existing.name != professor_name,
        existing.email != professor_email,
        existing.professor_personal_id != professor_personal_id,
        existing.professor_data != professor_data,
    ])


def build_institute_response(institute, published_professors, **extra):
    payload = OrderedDict([
        ('id', institute.id),
        ('name', institute.name),
        ('published_professors', published_professors),
    ])
    for key, value in extra.items():
        payload[key] = value
    return payload


class PublishedProfessorListView(APIView):
    permission_classes = [PublishedProfessorAdminKeyPermission]

    def _get_requested_professor_id(self, request):
        return request.query_params.get('professor_id') or request.data.get('professor_id')

    def _get_requested_professor_ids(self, request):
        if 'professor_ids' not in request.data:
            return None

        raw_ids = request.data.get('professor_ids')
        if not isinstance(raw_ids, list):
            raise ValueError('professor_ids must be a list of professor IDs.')

        professor_ids = []
        seen_ids = set()
        for raw_id in raw_ids:
            try:
                professor_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise ValueError('professor_ids must contain only valid professor IDs.') from exc

            if professor_id <= 0:
                raise ValueError('professor_ids must contain only valid professor IDs.')

            if professor_id not in seen_ids:
                professor_ids.append(professor_id)
                seen_ids.add(professor_id)

        return professor_ids

    def _sync_professor_snapshot(self, institute, professor, existing=None):
        professor_data = build_professor_snapshot(professor)
        professor_personal_id = get_professor_personal_id(professor_data)
        now = timezone.now()

        if existing is None:
            snapshot = PublishedProfessor.objects.create(
                institute_id=institute.id,
                source_professor_id=professor.id,
                name=professor.name,
                email=professor.email,
                professor_personal_id=professor_personal_id,
                professor_data=professor_data,
                published_at=now,
                updated_at=now,
            )
            return snapshot, 'created'

        if not snapshot_has_changed(
            existing,
            professor.name,
            professor.email,
            professor_personal_id,
            professor_data,
        ):
            return existing, 'already_exists'

        existing.name = professor.name
        existing.email = professor.email
        existing.professor_personal_id = professor_personal_id
        existing.professor_data = professor_data
        existing.updated_at = now
        existing.save(
            update_fields=['name', 'email', 'professor_personal_id', 'professor_data', 'updated_at']
        )
        return existing, 'updated'

    def _sync_professor_collection(self, institute, professors, delete_stale=False):
        existing_map = {
            snapshot.source_professor_id: snapshot
            for snapshot in PublishedProfessor.objects.filter(institute=institute).only(
                *PUBLISHED_ONLY_FIELDS,
            )
        }

        current_professor_ids = set()
        create_objects = []
        update_objects = []
        already_exists_professor_ids = []
        now = timezone.now()

        for professor in professors:
            current_professor_ids.add(professor.id)
            professor_data = build_professor_snapshot(professor)
            professor_personal_id = get_professor_personal_id(professor_data)
            existing = existing_map.get(professor.id)

            if existing is None:
                create_objects.append(
                    PublishedProfessor(
                        institute_id=institute.id,
                        source_professor_id=professor.id,
                        name=professor.name,
                        email=professor.email,
                        professor_personal_id=professor_personal_id,
                        professor_data=professor_data,
                        published_at=now,
                        updated_at=now,
                    )
                )
                continue

            if not snapshot_has_changed(
                existing,
                professor.name,
                professor.email,
                professor_personal_id,
                professor_data,
            ):
                already_exists_professor_ids.append(professor.id)
                continue

            existing.name = professor.name
            existing.email = professor.email
            existing.professor_personal_id = professor_personal_id
            existing.professor_data = professor_data
            existing.updated_at = now
            update_objects.append(existing)

        if create_objects:
            PublishedProfessor.objects.bulk_create(create_objects)
        if update_objects:
            PublishedProfessor.objects.bulk_update(
                update_objects,
                ['name', 'email', 'professor_personal_id', 'professor_data', 'updated_at'],
            )

        stale_professor_ids = set()
        if delete_stale:
            stale_professor_ids = set(existing_map).difference(current_professor_ids)
            if stale_professor_ids:
                PublishedProfessor.objects.filter(
                    institute=institute,
                    source_professor_id__in=stale_professor_ids,
                ).delete()

        response_kwargs = {
            'created_count': len(create_objects),
            'updated_count': len(update_objects),
            'already_exists_count': len(already_exists_professor_ids),
            'deleted_count': len(stale_professor_ids),
        }
        if already_exists_professor_ids:
            response_kwargs['message'] = ALREADY_EXISTS_MESSAGE
            response_kwargs['already_exists_professor_ids'] = already_exists_professor_ids
        if (
            not create_objects
            and not update_objects
            and not stale_professor_ids
            and already_exists_professor_ids
        ):
            response_kwargs['detail'] = ALREADY_EXISTS_MESSAGE

        return current_professor_ids, response_kwargs

    def get(self, request):
        institute = request._verified_institute
        serializer = PublishedProfessorSerializer(
            get_published_professor_queryset(institute),
            many=True,
        )
        return Response(build_institute_response(institute, serializer.data))

    def post(self, request):
        institute = request._verified_institute
        requested_professor_id = self._get_requested_professor_id(request)

        if requested_professor_id:
            try:
                professor = get_professor_publish_queryset(
                    institute,
                    professor_id=requested_professor_id,
                ).get()
            except Professor.DoesNotExist:
                return Response(
                    {'detail': 'Professor not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            existing = PublishedProfessor.objects.filter(
                institute=institute,
                source_professor_id=professor.id,
            ).only(*PUBLISHED_ONLY_FIELDS).first()
            snapshot, action = self._sync_professor_snapshot(institute, professor, existing=existing)
            serializer = PublishedProfessorSerializer(snapshot)

            response_kwargs = {
                'created_count': 1 if action == 'created' else 0,
                'updated_count': 1 if action == 'updated' else 0,
                'already_exists_count': 1 if action == 'already_exists' else 0,
                'deleted_count': 0,
            }
            if action == 'already_exists':
                response_kwargs['message'] = SINGLE_ALREADY_EXISTS_MESSAGE
                response_kwargs['detail'] = SINGLE_ALREADY_EXISTS_MESSAGE
                response_kwargs['already_exists_professor_ids'] = [professor.id]

            log_activity(
                request,
                action='sync',
                entity_type='published professor data',
                entity_id=professor.id,
                entity_name=professor.name,
                description=f"Synced published professor data for {professor.name}.",
                details=response_kwargs,
            )
            return Response(
                build_institute_response(
                    institute,
                    [serializer.data],
                    **response_kwargs,
                ),
                status=status.HTTP_200_OK,
            )

        try:
            requested_professor_ids = self._get_requested_professor_ids(request)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if requested_professor_ids is not None:
            if not requested_professor_ids:
                response_kwargs = {
                    'created_count': 0,
                    'updated_count': 0,
                    'already_exists_count': 0,
                    'deleted_count': 0,
                }
                return Response(
                    build_institute_response(institute, [], **response_kwargs),
                    status=status.HTTP_200_OK,
                )

            professors = list(
                get_professor_publish_queryset(institute)
                .filter(id__in=requested_professor_ids)
            )
            found_professor_ids = {professor.id for professor in professors}
            missing_professor_ids = [
                professor_id
                for professor_id in requested_professor_ids
                if professor_id not in found_professor_ids
            ]
            if missing_professor_ids:
                return Response(
                    {
                        'detail': 'Professor not found.',
                        'missing_professor_ids': missing_professor_ids,
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            synced_professor_ids, response_kwargs = self._sync_professor_collection(
                institute,
                professors,
                delete_stale=False,
            )
            serializer = PublishedProfessorSerializer(
                get_published_professor_queryset(institute).filter(
                    source_professor_id__in=synced_professor_ids,
                ),
                many=True,
            )

            log_activity(
                request,
                action='sync',
                entity_type='published professor data',
                description=(
                    f"Synced selected published professor data. Created {response_kwargs['created_count']}, "
                    f"updated {response_kwargs['updated_count']}."
                ),
                details={**response_kwargs, 'requested_professor_ids': requested_professor_ids},
            )
            return Response(
                build_institute_response(
                    institute,
                    serializer.data,
                    **response_kwargs,
                ),
                status=status.HTTP_200_OK,
            )

        professors = list(get_professor_publish_queryset(institute))
        _, response_kwargs = self._sync_professor_collection(
            institute,
            professors,
            delete_stale=True,
        )

        serializer = PublishedProfessorSerializer(
            get_published_professor_queryset(institute),
            many=True,
        )

        log_activity(
            request,
            action='sync',
            entity_type='published professor data',
            description=(
                f"Synced published professor data. Created {response_kwargs['created_count']}, "
                f"updated {response_kwargs['updated_count']}, removed {response_kwargs['deleted_count']}."
            ),
            details=response_kwargs,
        )
        return Response(
            build_institute_response(
                institute,
                serializer.data,
                **response_kwargs,
            ),
            status=status.HTTP_200_OK,
        )


class PublishedProfessorIdLookupView(APIView):
    permission_classes = [PublishedProfessorPersonalKeyPermission]

    def post(self, request):
        serializer = PublishedProfessorIdLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        institute = request._verified_institute
        personal_key = request._personal_key
        email = serializer.validated_data['email']

        try:
            snapshot = get_published_professor_lookup_queryset(institute).get(
                email=email,
                professor_personal_id=personal_key,
            )
        except PublishedProfessor.DoesNotExist:
            return Response(
                {'detail': 'Published professor not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                'professor_id': snapshot.source_professor_id,
                'institute': institute.id,
            },
            status=status.HTTP_200_OK,
        )


class PublishedProfessorDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [PublishedProfessorPersonalKeyPermission()]
        return [PublishedProfessorAdminKeyPermission()]

    def _get_snapshot(self, institute, professor_id):
        return get_published_professor_queryset(institute).get(source_professor_id=professor_id)

    def get(self, request, professor_id):
        institute = request._verified_institute
        try:
            snapshot = self._get_snapshot(institute, professor_id)
        except PublishedProfessor.DoesNotExist:
            return Response(
                {'detail': 'Published professor not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        self.check_object_permissions(request, snapshot)
        serializer = PublishedProfessorSerializer(snapshot)
        return Response(build_institute_response(institute, [serializer.data]))

    def patch(self, request, professor_id):
        return self._update(request, professor_id, partial=True)

    def put(self, request, professor_id):
        return self._update(request, professor_id, partial=False)

    def _update(self, request, professor_id, partial):
        institute = request._verified_institute
        try:
            snapshot = self._get_snapshot(institute, professor_id)
        except PublishedProfessor.DoesNotExist:
            return Response(
                {'detail': 'Published professor not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PublishedProfessorSerializer(snapshot, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        snapshot = serializer.save()
        log_activity(
            request,
            action='update',
            entity_type='published professor data',
            entity_id=snapshot.id,
            entity_name=snapshot.name,
            description=f"Updated published professor data for {snapshot.name}.",
            details={'professor_id': professor_id},
        )
        return Response(build_institute_response(institute, [PublishedProfessorSerializer(snapshot).data]))

    def delete(self, request, professor_id):
        institute = request._verified_institute
        try:
            snapshot = self._get_snapshot(institute, professor_id)
        except PublishedProfessor.DoesNotExist:
            return Response(
                {'detail': 'Published professor not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        deleted_payload = {'entity_id': snapshot.id, 'entity_name': snapshot.name}
        snapshot.delete()
        log_activity(
            request,
            action='delete',
            entity_type='published professor data',
            entity_id=deleted_payload['entity_id'],
            entity_name=deleted_payload['entity_name'],
            description=f"Deleted published professor data for {deleted_payload['entity_name']}.",
            details={'professor_id': professor_id},
        )
        return Response(
            build_institute_response(institute, [], deleted_professor_id=professor_id),
            status=status.HTTP_200_OK,
        )
