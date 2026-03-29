from rest_framework import serializers

from .models import InstituteTotalLeave, ProfessorLeave


def validate_context_published_professor(serializer, published_professor):
    institute = serializer.context['institute']
    if published_professor.institute_id != institute.id:
        raise serializers.ValidationError(
            'Published professor not found in the authenticated institute.'
        )

    verified_published_professor = serializer.context.get('verified_published_professor')
    if (
        verified_published_professor is not None
        and published_professor.id != verified_published_professor.id
    ):
        raise serializers.ValidationError(
            'You can only manage your own leave records with a personal key.'
        )
    return published_professor


def resolve_published_professor(serializer, attrs):
    verified_published_professor = serializer.context.get('verified_published_professor')
    if verified_published_professor is not None and 'published_professor' not in attrs:
        attrs['published_professor'] = verified_published_professor
    elif serializer.instance is None and 'published_professor' not in attrs:
        raise serializers.ValidationError(
            {'published_professor': ['This field is required.']}
        )
    return attrs.get('published_professor') or getattr(serializer.instance, 'published_professor', None)


def apply_published_professor_snapshot(instance, published_professor):
    professor_data = published_professor.professor_data or {}
    experience = professor_data.get('experience') or {}
    instance.professor_name = published_professor.name or professor_data.get('name', '')
    instance.department = experience.get('department', '')
    instance.email = published_professor.email or professor_data.get('email', '')


class ProfessorLeaveSerializer(serializers.ModelSerializer):
    professor_name = serializers.CharField(read_only=True)
    department = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    current_time = serializers.TimeField(read_only=True)
    total_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProfessorLeave
        fields = [
            'id',
            'published_professor',
            'professor_name',
            'department',
            'email',
            'start_date',
            'end_date',
            'current_time',
            'reason',
            'leaves_status',
            'cancellation_reason',
            'total_days',
        ]
        extra_kwargs = {
            'published_professor': {'required': False},
        }
        validators = []

    def validate_published_professor(self, published_professor):
        return validate_context_published_professor(self, published_professor)

    def validate(self, attrs):
        published_professor = resolve_published_professor(self, attrs)
        start_date = attrs.get('start_date') or getattr(self.instance, 'start_date', None)
        end_date = attrs.get('end_date') or getattr(self.instance, 'end_date', None)
        leaves_status = attrs.get(
            'leaves_status',
            getattr(self.instance, 'leaves_status', ProfessorLeave.LeaveStatus.PENDING),
        )
        cancellation_reason = attrs.get(
            'cancellation_reason',
            getattr(self.instance, 'cancellation_reason', ''),
        )
        institute = self.context['institute']

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {'end_date': ['end_date must be greater than or equal to start_date.']}
            )

        if leaves_status == ProfessorLeave.LeaveStatus.CANCELLED:
            if not (cancellation_reason or '').strip():
                raise serializers.ValidationError(
                    {'cancellation_reason': ['cancellation_reason is required when leaves_status is cancelled.']}
                )
        else:
            attrs['cancellation_reason'] = ''

        if published_professor and start_date and end_date:
            queryset = ProfessorLeave.objects.filter(
                institute=institute,
                published_professor=published_professor,
                start_date=start_date,
                end_date=end_date,
            )
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    'Leave already exists for this professor in the selected date range.'
                )

        return attrs

    def create(self, validated_data):
        validated_data['institute'] = self.context['institute']
        published_professor = validated_data['published_professor']
        leave = ProfessorLeave(**validated_data)
        apply_published_professor_snapshot(leave, published_professor)
        leave.save()
        return leave

    def update(self, instance, validated_data):
        published_professor = validated_data.get('published_professor', instance.published_professor)

        for field in (
            'published_professor',
            'start_date',
            'end_date',
            'reason',
            'leaves_status',
            'cancellation_reason',
        ):
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        apply_published_professor_snapshot(instance, published_professor)
        instance.save()
        return instance


class InstituteTotalLeaveSerializer(serializers.ModelSerializer):
    institute_name = serializers.CharField(source='institute.name', read_only=True)
    total_leaves = serializers.IntegerField(min_value=0)

    class Meta:
        model = InstituteTotalLeave
        fields = [
            'id',
            'institute',
            'institute_name',
            'total_leaves',
        ]
        read_only_fields = ('id', 'institute', 'institute_name')
        validators = []

    def validate(self, attrs):
        institute = self.context['institute']
        queryset = InstituteTotalLeave.objects.filter(institute=institute)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                'Total leaves setting already exists for this institute.'
            )
        return attrs

    def create(self, validated_data):
        validated_data['institute'] = self.context['institute']
        return super().create(validated_data)
