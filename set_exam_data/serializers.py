from rest_framework import serializers
from .models import ExamData, ObtainedMarks
from students.models import Student


class ExamDataItemSerializer(serializers.ModelSerializer):
    """Serializer for individual exam data entries (subjects)."""

    class Meta:
        model = ExamData
        fields = ['id', 'subject', 'exam_type', 'date', 'duration', 'total_marks']
        extra_kwargs = {'id': {'read_only': True}}


class ExamDataWriteSerializer(serializers.ModelSerializer):
    """Used for POST/PUT/PATCH on individual ExamData rows."""

    class Meta:
        model = ExamData
        fields = ['id', 'subject', 'exam_type', 'date', 'duration', 'total_marks']
        extra_kwargs = {'id': {'read_only': True}}


class ExamDictionarySerializer(serializers.Serializer):
    """
    Flat dictionary format response:
    {
        "institute": "ABC Institute",
        "institute_id": 1,
        "class": "10",
        "branch": "Science",
        "academic_terms": "Term 1",
        "exam_data": [ { id, subject, exam_type, date, duration, total_marks }, ... ]
    }
    """
    institute_id = serializers.IntegerField(source='institute.id', read_only=True)
    institute = serializers.CharField(source='institute.institute_name', read_only=True)
    class_name = serializers.CharField(read_only=True)
    branch = serializers.CharField(read_only=True)
    academic_term = serializers.CharField(read_only=True)

    def to_representation(self, data):
        """
        `data` is a dict built by the view:
          { 'institute': <Institute>, 'class_name', 'branch', 'academic_term', 'exam_data': queryset }
        """
        return {
            'institute': data['institute'].institute_name,
            'institute_id': data['institute'].id,
            'class': data['class_name'],
            'branch': data['branch'],
            'academic_terms': data['academic_term'],
            'exam_data': ExamDataItemSerializer(data['exam_data'], many=True).data,
        }


class ObtainedMarksSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    subject = serializers.CharField(source='exam_data.subject', read_only=True)
    class_name = serializers.CharField(source='exam_data.class_name', read_only=True)
    branch = serializers.CharField(source='exam_data.branch', read_only=True)
    academic_term = serializers.CharField(source='exam_data.academic_term', read_only=True)
    exam_type = serializers.CharField(source='exam_data.exam_type', read_only=True)

    class Meta:
        model = ObtainedMarks
        fields = [
            'id', 'exam_data', 'subject', 'class_name', 'branch',
            'academic_term', 'exam_type', 'student', 'student_name',
            'obtained_marks',
        ]
        extra_kwargs = {'id': {'read_only': True}}

    def validate(self, attrs):
        exam_data = attrs.get('exam_data') or getattr(self.instance, 'exam_data', None)
        student = attrs.get('student') or getattr(self.instance, 'student', None)
        obtained_marks = attrs.get('obtained_marks')

        if obtained_marks is None and self.instance is not None:
            obtained_marks = self.instance.obtained_marks

        if exam_data is not None and obtained_marks is not None and obtained_marks > exam_data.total_marks:
            raise serializers.ValidationError({
                'obtained_marks': [
                    f'Obtained marks cannot be greater than total marks ({exam_data.total_marks}).'
                ]
            })

        if student is not None and exam_data is not None and student.institute_id != exam_data.institute_id:
            raise serializers.ValidationError({
                'student': ['Student must belong to the same institute as the exam.']
            })

        return attrs
