import hmac

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from institute_api.permissions import (
    ADMIN_ACCESS_CONTROL,
    cache_verified_admin_request,
    get_request_admin_key,
    get_verified_institute,
    verify_admin_key_for_institute,
)


class ProfessorLeavesPermission(BasePermission):
    message = 'Provide X-Admin-Key for institute access or X-Personal-Key (15 chars).'

    def _get_institute_id(self, request):
        return (
            request.query_params.get('institute')
            or (request.data.get('institute') if hasattr(request, 'data') else None)
        )

    def has_permission(self, request, view):
        from published_professors.models import PublishedProfessor

        admin_key = request.headers.get('X-Admin-Key')
        personal_key = request.headers.get('X-Personal-Key')

        if not admin_key and not personal_key:
            raise PermissionDenied(self.message)

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (?institute= query param or body field).')

        institute = get_verified_institute(request)

        if admin_key:
            try:
                verify_admin_key_for_institute(
                    request,
                    institute,
                    view=view,
                    message='Invalid admin key for this institute.',
                    admin_key=admin_key,
                    allowed_subordinate_access_controls=(ADMIN_ACCESS_CONTROL,),
                )
                return True
            except PermissionDenied:
                if not personal_key:
                    raise

        if personal_key:
            if len(personal_key) != 15:
                raise PermissionDenied('Provide X-Personal-Key with exactly 15 characters.')

            try:
                published_professor = PublishedProfessor.objects.only(
                    'id',
                    'institute_id',
                    'professor_personal_id',
                ).get(
                    institute_id=institute.id,
                    professor_personal_id=personal_key,
                )
            except PublishedProfessor.DoesNotExist:
                raise PermissionDenied('No published professor found with the given personal key.')

            request._verified_institute = institute
            request._personal_key = personal_key
            request._verified_published_professor = published_professor
            return True

        raise PermissionDenied(self.message)

    def has_object_permission(self, request, view, obj):
        verified_published_professor = getattr(request, '_verified_published_professor', None)
        if verified_published_professor is None:
            return True

        return (
            obj.institute_id == request._verified_institute.id
            and obj.published_professor_id == verified_published_professor.id
        )


class InstituteTotalLeavesPermission(ProfessorLeavesPermission):
    message = (
        'Read access requires a 29-32 character institute access key or a '
        '15-character personal key. Saving requires the exact 32-character '
        'institute admin key.'
    )
    read_access_key_lengths = {29, 30, 31, 32}

    def has_permission(self, request, view):
        institute = get_verified_institute(request)

        if request.method in SAFE_METHODS:
            return self._has_read_permission(request, view, institute)

        return self._has_write_permission(request, institute)

    def _has_read_permission(self, request, view, institute):
        from published_professors.models import PublishedProfessor

        admin_key = get_request_admin_key(request)
        personal_key = request.headers.get('X-Personal-Key')

        if not admin_key and not personal_key:
            raise PermissionDenied(self.message)

        if admin_key and len(str(admin_key)) in self.read_access_key_lengths:
            try:
                verify_admin_key_for_institute(
                    request,
                    institute,
                    view=view,
                    message='Invalid institute access key for this institute.',
                    admin_key=admin_key,
                    allowed_subordinate_access_controls=(ADMIN_ACCESS_CONTROL,),
                )
                return True
            except PermissionDenied:
                if not personal_key:
                    raise
        elif admin_key and not personal_key:
            raise PermissionDenied(
                'Provide X-Admin-Key with 29, 30, 31, or 32 characters for read access.'
            )

        if personal_key:
            if len(personal_key) != 15:
                raise PermissionDenied('Provide X-Personal-Key with exactly 15 characters.')

            try:
                published_professor = PublishedProfessor.objects.only(
                    'id',
                    'institute_id',
                    'professor_personal_id',
                ).get(
                    institute_id=institute.id,
                    professor_personal_id=personal_key,
                )
            except PublishedProfessor.DoesNotExist:
                raise PermissionDenied('No published professor found with the given personal key.')

            request._verified_institute = institute
            request._personal_key = personal_key
            request._verified_published_professor = published_professor
            return True

        raise PermissionDenied(self.message)

    def _has_write_permission(self, request, institute):
        admin_key = get_request_admin_key(request) or ''

        if len(admin_key) != 32:
            raise PermissionDenied(
                'Saving institute session defaults requires the exact 32-character admin key.'
            )

        if not hmac.compare_digest(str(institute.admin_key or ''), str(admin_key)):
            raise PermissionDenied(
                'Saving institute session defaults requires the exact 32-character admin key.'
            )

        cache_verified_admin_request(request, institute, admin_key)
        return True

    def has_object_permission(self, request, view, obj):
        return obj.institute_id == request._verified_institute.id
