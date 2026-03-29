from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class ProfessorLeavesPermission(BasePermission):
    message = 'Provide X-Admin-Key (32 chars) or X-Personal-Key (15 chars).'

    def _get_institute_id(self, request):
        return (
            request.query_params.get('institute')
            or (request.data.get('institute') if hasattr(request, 'data') else None)
        )

    def has_permission(self, request, view):
        from iinstitutes_list.models import Institute
        from published_professors.models import PublishedProfessor

        admin_key = request.headers.get('X-Admin-Key')
        personal_key = request.headers.get('X-Personal-Key')

        if not admin_key and not personal_key:
            raise PermissionDenied(self.message)

        institute_id = self._get_institute_id(request)
        if not institute_id:
            raise PermissionDenied('institute id is required (?institute= query param or body field).')

        try:
            institute = Institute.objects.only('id', 'name', 'admin_key', 'event_status').get(pk=institute_id)
        except Institute.DoesNotExist:
            raise PermissionDenied('Institute not found.')

        if institute.event_status != 'active':
            raise PermissionDenied(
                f'Institute events are currently {institute.event_status}. Access denied.'
            )

        if admin_key:
            if len(admin_key) != 32:
                if not personal_key:
                    raise PermissionDenied('Provide X-Admin-Key with exactly 32 characters.')
            elif institute.admin_key == admin_key:
                request._verified_institute = institute
                request._admin_key = admin_key
                return True
            elif not personal_key:
                raise PermissionDenied('Invalid admin key for this institute.')

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
    def has_object_permission(self, request, view, obj):
        return obj.institute_id == request._verified_institute.id
