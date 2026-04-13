from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from attendance.models import Attendance
from iinstitutes_list.models import Institute
from set_exam_data.models import ExamData, ObtainedMarks
from students.models import (
    Student,
    StudentAdmissionDetails,
    StudentContactDetails,
    StudentCourseAssignment,
    StudentEducationDetails,
    StudentFeeDetails,
    StudentSystemDetails,
    SubjectsAssigned,
)


CLASS_NAME = 'B.A'
BRANCH = 'History'
ACADEMIC_TERM = '2nd Semester'
ACADEMIC_YEAR = '2025-2026'
ATTENDANCE_DAYS = 365
TOTAL_FEE_AMOUNT = 48000

SEMESTER_SUBJECTS = [
    'History of Medieval India',
    'History of Europe 1453-1789',
    'Social Formations and Cultural Patterns',
    'Political Theory',
    'English Communication II',
    'Environmental Studies',
]

ASSIGNED_SUBJECTS = [
    'Medieval India',
    'Europe 1453-1789',
    'Social Formations',
    'Political Theory',
    'English Comm II',
    'Env Studies',
]

EXAM_TYPES = [
    ('Internal', 40),
    ('Final', 100),
]

STUDENT_NAMES = [
    'Aarav Sharma',
    'Diya Singh',
    'Kabir Verma',
    'Meera Das',
]


class Command(BaseCommand):
    help = (
        'Create 4 dummy B.A History 2nd Semester students with one year of attendance, '
        'fully paid fees, and passing exam marks without sending any email notifications.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=4,
            help='Number of students to create. Defaults to 4.',
        )
        parser.add_argument(
            '--institute-id',
            type=int,
            help='Institute ID to attach the dummy students to. Defaults to the first active institute.',
        )
        parser.add_argument(
            '--attendance-days',
            type=int,
            default=ATTENDANCE_DAYS,
            help='Number of days of attendance history to generate. Defaults to 365.',
        )

    def _get_institute(self, institute_id):
        if institute_id is not None:
            try:
                institute = Institute.objects.get(pk=institute_id)
            except Institute.DoesNotExist as exc:
                raise CommandError(f'Institute with id={institute_id} was not found.') from exc
            return institute

        institute = Institute.objects.filter(event_status='active').order_by('id').first()
        if institute is None:
            raise CommandError('No active institute found. Create or activate an institute before seeding students.')
        return institute

    def _build_identity_number(self, seed_number):
        return f'{700000000000 + seed_number}'

    def _build_mobile_number(self, seed_number):
        return f'9{800000000 + seed_number:09d}'

    def _build_personal_id(self, seed_number):
        return f'HIST{seed_number:011d}'

    def _build_library_id(self, seed_number):
        return f'LIBHIS{seed_number:06d}'

    def _create_exam_data(self, institute, base_exam_date):
        exams = []
        for subject_index, subject in enumerate(SEMESTER_SUBJECTS):
            for exam_type_index, (exam_type, total_marks) in enumerate(EXAM_TYPES):
                exam_date = base_exam_date + timedelta(days=(subject_index * 4) + exam_type_index)
                exam, _ = ExamData.objects.get_or_create(
                    institute=institute,
                    class_name=CLASS_NAME,
                    branch=BRANCH,
                    academic_term=ACADEMIC_TERM,
                    subject=subject,
                    exam_type=exam_type,
                    defaults={
                        'date': exam_date,
                        'duration': 90 if exam_type == 'Internal' else 180,
                        'total_marks': total_marks,
                    },
                )
                exams.append(exam)
        return exams

    def _create_attendance_rows(self, student, attendance_days):
        today = date.today()
        first_day = today - timedelta(days=attendance_days - 1)
        attendance_rows = []

        for day_offset in range(attendance_days):
            current_date = first_day + timedelta(days=day_offset)
            if current_date.weekday() == 6:
                continue

            attendance_rows.append(
                Attendance(
                    student=student,
                    date=current_date,
                    class_name=CLASS_NAME,
                    branch=BRANCH,
                    year_semester=ACADEMIC_TERM,
                    status=(day_offset % 17) != 0,
                    marked_by=None,
                )
            )

        Attendance.objects.bulk_create(attendance_rows)
        return len(attendance_rows)

    def _create_subject_rows(self, student):
        subject_rows = [
            SubjectsAssigned(
                student=student,
                subject=subject,
                unit=str(index + 1),
            )
            for index, subject in enumerate(ASSIGNED_SUBJECTS)
        ]
        SubjectsAssigned.objects.bulk_create(subject_rows)

    def _create_marks_rows(self, student, exams, student_offset):
        marks_rows = []
        for exam_index, exam in enumerate(exams):
            if exam.total_marks <= 40:
                obtained_marks = 28 + ((student_offset + exam_index) % 8)
            else:
                obtained_marks = 64 + ((student_offset + exam_index) % 18)

            marks_rows.append(
                ObtainedMarks(
                    exam_data=exam,
                    student=student,
                    obtained_marks=obtained_marks,
                )
            )

        ObtainedMarks.objects.bulk_create(marks_rows)
        return len(marks_rows)

    def handle(self, *args, **options):
        count = options['count']
        attendance_days = options['attendance_days']

        if count <= 0:
            raise CommandError('--count must be greater than 0.')
        if attendance_days <= 0:
            raise CommandError('--attendance-days must be greater than 0.')

        institute = self._get_institute(options.get('institute_id'))
        starting_index = (Student.objects.order_by('-id').values_list('id', flat=True).first() or 0) + 1
        base_exam_date = date.today() - timedelta(days=45)

        created_students = []
        attendance_count = 0
        marks_count = 0

        with transaction.atomic():
            exams = self._create_exam_data(institute, base_exam_date)
            for offset in range(count):
                seed_number = starting_index + offset
                student_name = STUDENT_NAMES[offset % len(STUDENT_NAMES)]
                student = Student.objects.create(
                    institute=institute,
                    name=f'{student_name} {seed_number:03d}',
                    dob=date(2004, ((offset + 1) % 12) + 1, min(10 + offset, 28)),
                    gender='Female' if offset % 2 else 'Male',
                    nationality='Indian',
                    identity=self._build_identity_number(seed_number),
                    category='General',
                )
                created_students.append(student)

                StudentContactDetails.objects.create(
                    student=student,
                    email=f'ba.history.{seed_number:04d}@dummy.local',
                    permanent_address=f'History Lane {seed_number}, Kolkata',
                    current_address=f'History Lane {seed_number}, Kolkata',
                    mobile=self._build_mobile_number(seed_number),
                    father_name=f'Parent {seed_number:03d}',
                    mother_name=f'Mother {seed_number:03d}',
                    guardian_name=f'Guardian {seed_number:03d}',
                    parent_contact=self._build_mobile_number(seed_number + 5000),
                )
                StudentEducationDetails.objects.create(
                    student=student,
                    qualification='12th Pass',
                    passing_year=2024,
                    institute_name='Dummy Higher Secondary School',
                    marks_obtained='82%',
                )
                StudentAdmissionDetails.objects.create(
                    student=student,
                    enrollment_number=f'BAHISTENR{seed_number:04d}',
                    roll_number=f'BAHISTROL{seed_number:04d}',
                    admission_date=date.today() - timedelta(days=300),
                    academic_year=ACADEMIC_YEAR,
                )
                StudentCourseAssignment.objects.create(
                    student=student,
                    class_name=CLASS_NAME,
                    branch=BRANCH,
                    academic_term=ACADEMIC_TERM,
                )
                StudentFeeDetails.objects.create(
                    student=student,
                    total_fee_amount=TOTAL_FEE_AMOUNT,
                    paid_amount=TOTAL_FEE_AMOUNT,
                    pending_amount=0,
                )
                StudentSystemDetails.objects.create(
                    student=student,
                    student_personal_id=self._build_personal_id(seed_number),
                    library_card_number=self._build_library_id(seed_number),
                    hostel_details='Day Scholar',
                    verification_status='verified',
                )

                self._create_subject_rows(student)
                attendance_count += self._create_attendance_rows(student, attendance_days)
                marks_count += self._create_marks_rows(student, exams, offset)

        self.stdout.write(
            self.style.SUCCESS(
                f'Created {len(created_students)} dummy students for institute "{institute.name}" '
                f'(id={institute.id}) in {CLASS_NAME} / {BRANCH} / {ACADEMIC_TERM}. '
                f'Created {attendance_count} attendance rows, {len(exams)} exam entries, and {marks_count} passing marks rows. '
                'No email notifications were sent.'
            )
        )
