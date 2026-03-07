from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import StuentUniqueId, ProfessorUniqueId
from .serializers import StudentUniqueIdSerializer, ProfessorUniqueIdSerializer
# from students.models import Student,StudentContactDetails,StudentSystemDetails
# from professors.models import Professor,professorAdminEmployement

class StudentUniqueIdViewSet(ModelViewSet):
    queryset = StuentUniqueId.objects.all()
    serializer_class = StudentUniqueIdSerializer

class ProfessorUniqueIdViewSet(ModelViewSet):
    queryset = ProfessorUniqueId.objects.all()
    serializer_class = ProfessorUniqueIdSerializer

# class StudentUniqueIdAPIView(APIView):
#     def get(self, request):
#         students = Student.objects.all()
#         serializer = StuentUniqueIdSerializer(students, many=True)
#         return Response(serializer.data)

# class ProfessorUniqueIdAPIView(APIView):
#     def get(self, request):
#         professors = Professor.objects.all()
#         serializer = ProfessorUniqueIdSerializer(professors, many=True)
#         return Response(serializer.data)

# Create your views here.
