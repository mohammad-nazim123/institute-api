from datetime import datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Min, Q
from django.utils import timezone

from attendance.models import AttendanceSubmission
from iinstitutes_list.models import Institute
from professor_attendance.models import ProfessorAttendance
from professors.models import Professor
from students.models import Student

from .create_dummy_ba_history_first_semester_demo import (
    ACADEMIC_TERM,
    BRANCH_NAME,
    CHECKIN_OFFSETS_MINUTES,
    CLASS_NAME,
    OPENING_TIME,
    PROFESSOR_PROFILES,
)


PROFILE_PREFIX_TO_INDEX = {
    profile['name']: index
    for index, profile in enumerate(PROFESSOR_PROFILES)
}


class Command(BaseCommand):
    help = (
        'Backfill daily professor attendance time and student attendance submission '
        'timestamps for the BA History 1st Semester demo data created for '
        'Arindam, Nandita, and Poulomi.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--institute-id',
            type=int,
            help='Only update demo data in the given institute.',
        )

    def _get_institutes(self, institute_id):
        if institute_id is not None:
            try:
                return [Institute.objects.get(pk=institute_id)]
            except Institute.DoesNotExist as exc:
                raise CommandError(f'Institute with id={institute_id} was not found.') from exc

        professor_filter = Q()
        for name_prefix in PROFILE_PREFIX_TO_INDEX:
            professor_filter |= Q(name__startswith=name_prefix)

        institute_ids = list(
            Professor.objects
            .filter(email__startswith='ba.history.prof')
            .filter(professor_filter)
            .values_list('institute_id', flat=True)
            .distinct()
        )
        return list(Institute.objects.filter(id__in=institute_ids).order_by('id'))

    def _build_checkin_time(self, entity_offset, day_offset):
        offset_minutes = CHECKIN_OFFSETS_MINUTES[
            (entity_offset + day_offset) % len(CHECKIN_OFFSETS_MINUTES)
        ]
        total_minutes = (OPENING_TIME.hour * 60) + OPENING_TIME.minute + offset_minutes
        hour, minute = divmod(total_minutes, 60)
        return time(hour=hour, minute=minute)

    def _get_dummy_professors(self, institute):
        professor_filter = Q()
        for name_prefix in PROFILE_PREFIX_TO_INDEX:
            professor_filter |= Q(name__startswith=name_prefix)

        return list(
            Professor.objects
            .filter(
                institute=institute,
                email__startswith='ba.history.prof',
            )
            .filter(professor_filter)
            .order_by('id')
        )

    def _get_professor_offset(self, professor):
        for name_prefix, index in PROFILE_PREFIX_TO_INDEX.items():
            if professor.name.startswith(name_prefix):
                return index
        return 0

    def _get_dummy_student_ids(self, institute):
        return list(
            Student.objects
            .filter(
                institute=institute,
                contact_details__email__startswith='ba.history.student',
                course_assignments__class_name=CLASS_NAME,
                course_assignments__branch=BRANCH_NAME,
                course_assignments__academic_term=ACADEMIC_TERM,
            )
            .values_list('id', flat=True)
        )

    def _get_first_demo_date(self, institute, professor_ids, student_ids):
        candidate_dates = []

        professor_first_date = (
            ProfessorAttendance.objects
            .filter(institute=institute, professor_id__in=professor_ids)
            .aggregate(first_date=Min('date'))
            .get('first_date')
        )
        if professor_first_date is not None:
            candidate_dates.append(professor_first_date)

        if student_ids:
            submission_first_date = (
                AttendanceSubmission.objects
                .filter(
                    institute=institute,
                    class_name=CLASS_NAME,
                    branch=BRANCH_NAME,
                    year_semester=ACADEMIC_TERM,
                    attendance_records__student_id__in=student_ids,
                )
                .aggregate(first_date=Min('date'))
                .get('first_date')
            )
            if submission_first_date is not None:
                candidate_dates.append(submission_first_date)

        return min(candidate_dates) if candidate_dates else None

    def _backfill_professor_attendance(self, institute, professors, first_day):
        update_count = 0
        professor_offset_by_id = {
            professor.id: self._get_professor_offset(professor)
            for professor in professors
        }

        attendances = (
            ProfessorAttendance.objects
            .filter(institute=institute, professor_id__in=professor_offset_by_id)
            .order_by('professor_id', 'date', 'id')
        )

        for attendance in attendances:
            day_offset = (attendance.date - first_day).days
            attendance_time = self._build_checkin_time(
                professor_offset_by_id.get(attendance.professor_id, 0),
                day_offset,
            )
            if attendance.attendance_time == attendance_time:
                continue

            attendance.attendance_time = attendance_time
            attendance.save(update_fields=['attendance_time'])
            update_count += 1

        return update_count

    def _backfill_student_submissions(self, institute, professors, student_ids, first_day):
        if not student_ids or not professors:
            return 0

        current_timezone = timezone.get_current_timezone()
        professor_ids = {professor.id for professor in professors}
        ordered_professors = sorted(
            professors,
            key=self._get_professor_offset,
        )

        submissions = (
            AttendanceSubmission.objects
            .filter(
                institute=institute,
                class_name=CLASS_NAME,
                branch=BRANCH_NAME,
                year_semester=ACADEMIC_TERM,
                attendance_records__student_id__in=student_ids,
            )
            .distinct()
            .order_by('date', 'id')
        )

        update_count = 0
        for submission in submissions:
            day_offset = (submission.date - first_day).days
            attendance_time = self._build_checkin_time(len(ordered_professors), day_offset)
            submitted_at = timezone.make_aware(
                datetime.combine(submission.date, attendance_time),
                current_timezone,
            )

            update_fields = []
            if submission.attendance_time != attendance_time:
                submission.attendance_time = attendance_time
                update_fields.append('attendance_time')
            if submission.submitted_at != submitted_at:
                submission.submitted_at = submitted_at
                update_fields.append('submitted_at')
            if submission.marked_by_id not in professor_ids:
                submission.marked_by = ordered_professors[day_offset % len(ordered_professors)]
                update_fields.append('marked_by')

            if not update_fields:
                continue

            submission.save(update_fields=update_fields)
            update_count += 1

        return update_count

    def handle(self, *args, **options):
        institutes = self._get_institutes(options.get('institute_id'))
        updated_professor_attendance = 0
        updated_student_submissions = 0
        matched_institutes = 0

        for institute in institutes:
            professors = self._get_dummy_professors(institute)
            if not professors:
                continue

            student_ids = self._get_dummy_student_ids(institute)
            first_day = self._get_first_demo_date(
                institute,
                [professor.id for professor in professors],
                student_ids,
            )
            if first_day is None:
                continue

            with transaction.atomic():
                matched_institutes += 1
                updated_professor_attendance += self._backfill_professor_attendance(
                    institute,
                    professors,
                    first_day,
                )
                updated_student_submissions += self._backfill_student_submissions(
                    institute,
                    professors,
                    student_ids,
                    first_day,
                )

        if matched_institutes == 0:
            raise CommandError(
                'No BA History 1st Semester demo professors were found for Arindam, Nandita, and Poulomi.'
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Updated {updated_professor_attendance} professor attendance rows and '
                f'{updated_student_submissions} student attendance submissions across '
                f'{matched_institutes} institute(s).'
            )
        )
