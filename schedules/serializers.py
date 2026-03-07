from rest_framework import serializers
from .models import WeeklySchedule,ExamSchedule,WeeklyScheduleData,WeeklyScheduleDay,ExamScheduleDate,ExamScheduleData

class WeeklyScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklySchedule
        fields = '__all__'
    
    def create(self, validated_data):
        return WeeklySchedule.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        instance.start_time = validated_data.get('start_time', instance.start_time)
        instance.end_time = validated_data.get('end_time', instance.end_time)
        instance.day = validated_data.get('day', instance.day)
        instance.subject = validated_data.get('subject', instance.subject)
        instance.classes = validated_data.get('classes', instance.classes)
        instance.room_number = validated_data.get('room_number', instance.room_number)
        instance.professor = validated_data.get('professor', instance.professor)
        instance.save()
        return instance

class ExamScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSchedule
        fields = '__all__'
    
    def create(self, validated_data):
        return ExamSchedule.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        instance.start_time = validated_data.get('start_time', instance.start_time)
        instance.end_time = validated_data.get('end_time', instance.end_time)
        instance.subject = validated_data.get('subject', instance.subject)
        instance.classes = validated_data.get('classes', instance.classes)
        instance.room_number = validated_data.get('room_number', instance.room_number)
        instance.exam_date = validated_data.get('exam_date', instance.exam_date)
        instance.type = validated_data.get('type', instance.type)
        instance.save()
        return instance


class WeeklyScheduleDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyScheduleData
        exclude = ['weekly_schedule_day']


class WeeklyScheduleDaySerializer(serializers.ModelSerializer):
    weekly_schedule_data = WeeklyScheduleDataSerializer(many=True,required=False)
    class Meta:
        model = WeeklyScheduleDay
        fields = '__all__'
    
    def create(self, validated_data):
        weekly_schedule_data = validated_data.pop('weekly_schedule_data', [])
        day_value = validated_data.get('day')
        
        # Get existing day or create a new one to extend its dictionary of data
        weekly_schedule_day, created = WeeklyScheduleDay.objects.get_or_create(
            day=day_value,
            defaults=validated_data
        )
        
        for data in weekly_schedule_data:
            WeeklyScheduleData.objects.create(weekly_schedule_day=weekly_schedule_day, **data)
        return weekly_schedule_day

class ExamScheduleDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamScheduleData
        exclude = ['exam_schedule_date']

class ExamScheduleDateSerializer(serializers.ModelSerializer):
    exam_schedule_data = ExamScheduleDataSerializer(many=True, required=False)
    
    class Meta:
        model = ExamScheduleDate
        fields = '__all__'
        
    def create(self, validated_data):
        exam_schedule_data = validated_data.pop('exam_schedule_data', [])
        date_value = validated_data.get('date')
        
        # Get existing date or create a new one to extend its dictionary of data
        exam_schedule_date, created = ExamScheduleDate.objects.get_or_create(
            date=date_value,
            defaults=validated_data
        )
        
        for data in exam_schedule_data:
            ExamScheduleData.objects.create(exam_schedule_date=exam_schedule_date, **data)
        return exam_schedule_date