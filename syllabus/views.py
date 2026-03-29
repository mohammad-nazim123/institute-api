from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from institute_api.permissions import InstituteKeyPermission
from .models import Course, Branch, AcademicTerms, Subject
from .serializers import CourseSerializer


class CourseView(APIView):
    """
    Full CRUD for Course with nested Branch > AcademicTerms > Subject.

    Auth: X-Admin-Key (32-char institute admin key).

    GET    /syllabus/course/?institute=<id>       → list all courses (nested)
    GET    /syllabus/course/<pk>/?institute=<id>  → retrieve one course
    POST   /syllabus/course/?institute=<id>       → create course (with nested data)
    PUT    /syllabus/course/<pk>/?institute=<id>  → full update
    PATCH  /syllabus/course/<pk>/?institute=<id>  → partial update
    DELETE /syllabus/course/<pk>/?institute=<id>  → delete
    """
    permission_classes = [InstituteKeyPermission]

    def _get_queryset(self, institute):
        return Course.objects.filter(institute=institute).prefetch_related(
            'branches__academic_terms__subjects'
        )

    # ── GET ───────────────────────────────────────────────────────────────────
    def get(self, request, pk=None):
        institute = request._verified_institute

        if pk is not None:
            try:
                course = self._get_queryset(institute).get(pk=pk)
            except Course.DoesNotExist:
                return Response({'detail': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(CourseSerializer(course).data)

        courses = self._get_queryset(institute)
        return Response(CourseSerializer(courses, many=True).data)

    # ── POST ──────────────────────────────────────────────────────────────────
    def post(self, request):
        institute = request._verified_institute
        data = {**request.data, 'institute': institute.pk}
        serializer = CourseSerializer(data=data)
        if serializer.is_valid():
            course = serializer.save()
            # Re-fetch with full nesting for response
            course = self._get_queryset(institute).get(pk=course.pk)
            return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── PUT ───────────────────────────────────────────────────────────────────
    def put(self, request, pk):
        institute = request._verified_institute
        try:
            course = self._get_queryset(institute).get(pk=pk)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = {**request.data, 'institute': institute.pk}
        serializer = CourseSerializer(course, data=data)
        if serializer.is_valid():
            serializer.save()
            course = self._get_queryset(institute).get(pk=pk)
            return Response(CourseSerializer(course).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── PATCH ─────────────────────────────────────────────────────────────────
    def patch(self, request, pk):
        institute = request._verified_institute
        try:
            course = self._get_queryset(institute).get(pk=pk)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = {**request.data, 'institute': institute.pk}
        serializer = CourseSerializer(course, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            course = self._get_queryset(institute).get(pk=pk)
            return Response(CourseSerializer(course).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── DELETE ────────────────────────────────────────────────────────────────
    def delete(self, request, pk):
        institute = request._verified_institute
        try:
            course = Course.objects.get(pk=pk, institute=institute)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)
        course.delete()
        return Response({'detail': 'Course deleted.'}, status=status.HTTP_200_OK)
