from rest_framework import serializers
from .models import Course, Subject



class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['name','unit']


class CourseSerializer(serializers.ModelSerializer):
    subjects = SubjectSerializer(many=True, required=False)
    class Meta:
        model = Course
        fields = ['id', 'institute', 'name', 'subjects']
        extra_kwargs = {
            'id': {'read_only': True},
        }

    def create(self, validated_data):
        subjects_data = validated_data.pop('subjects', [])
        course, created = Course.objects.get_or_create(
            name=validated_data.get('name'),
            institute=validated_data.get('institute')
        )
        for subjects_item in subjects_data:
            Subject.objects.create(course=course, **subjects_item)
        return course
        