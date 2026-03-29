from rest_framework import serializers
from django.db import transaction
from .models import Course, Branch, AcademicTerms, Subject


# ── Level 4: Subject ────────────────────────────────────────────────────────
class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'unit']
        extra_kwargs = {'id': {'read_only': True}}


# ── Level 3: AcademicTerms ──────────────────────────────────────────────────
class AcademicTermsSerializer(serializers.ModelSerializer):
    subjects = SubjectSerializer(many=True, required=False)

    class Meta:
        model = AcademicTerms
        fields = ['id', 'name', 'subjects']
        extra_kwargs = {'id': {'read_only': True}}


# ── Level 2: Branch ─────────────────────────────────────────────────────────
class BranchSerializer(serializers.ModelSerializer):
    academic_terms = AcademicTermsSerializer(many=True, required=False)

    class Meta:
        model = Branch
        fields = ['id', 'name', 'academic_terms']
        extra_kwargs = {'id': {'read_only': True}}


# ── Level 1: Course (root) ──────────────────────────────────────────────────
class CourseSerializer(serializers.ModelSerializer):
    branches = BranchSerializer(many=True, required=False)

    class Meta:
        model = Course
        fields = ['id', 'institute', 'name', 'branches']
        extra_kwargs = {'id': {'read_only': True}}

    # ── helpers ──────────────────────────────────────────────────────────────
    def _save_subjects(self, term, subjects_data):
        to_create = []
        for item in subjects_data:
            subject_id = item.pop('id', None)
            if subject_id:
                Subject.objects.filter(pk=subject_id, academic_terms=term).update(**item)
            else:
                to_create.append(Subject(academic_terms=term, **item))
        if to_create:
            Subject.objects.bulk_create(to_create)

    def _save_academic_terms(self, branch, terms_data):
        for item in terms_data:
            subjects_data = item.pop('subjects', [])
            term_id = item.pop('id', None)
            if term_id:
                AcademicTerms.objects.filter(pk=term_id, branch=branch).update(**item)
                term = AcademicTerms(pk=term_id, branch=branch, **item)
            else:
                term = AcademicTerms.objects.create(branch=branch, **item)
            self._save_subjects(term, subjects_data)

    def _save_branches(self, course, branches_data):
        for item in branches_data:
            terms_data = item.pop('academic_terms', [])
            branch_id = item.pop('id', None)
            if branch_id:
                Branch.objects.filter(pk=branch_id, course=course).update(**item)
                branch = Branch(pk=branch_id, course=course, **item)
            else:
                branch = Branch.objects.create(course=course, **item)
            self._save_academic_terms(branch, terms_data)

    # ── create ───────────────────────────────────────────────────────────────
    def create(self, validated_data):
        branches_data = validated_data.pop('branches', [])
        with transaction.atomic():
            course = Course.objects.create(**validated_data)
            self._save_branches(course, branches_data)
        return course

    # ── update ───────────────────────────────────────────────────────────────
    def update(self, instance, validated_data):
        branches_data = validated_data.pop('branches', None)
        with transaction.atomic():
            update_fields = []
            if 'name' in validated_data:
                instance.name = validated_data['name']
                update_fields.append('name')
            if 'institute' in validated_data:
                instance.institute = validated_data['institute']
                update_fields.append('institute')
            if update_fields:
                instance.save(update_fields=update_fields)
            if branches_data is not None:
                self._save_branches(instance, branches_data)
        return instance