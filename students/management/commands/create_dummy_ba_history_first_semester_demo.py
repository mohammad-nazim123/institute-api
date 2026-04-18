from datetime import date, datetime, time, timedelta
import math

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from activity_feed.models import ActivityEvent
from attendance.models import Attendance, AttendanceSubmission
from iinstitutes_list.models import Institute
from institute_api.permissions import ADMIN_ACCESS_CONTROL, FEE_ACCESS_CONTROL
from payments.models import ProfessorsPayments
from professor_attendance.models import ProfessorAttendance
from professor_leaves.models import (
    InstituteTotalLeave,
    ProfessorLeave as PublishedProfessorLeave,
)
from professors.serializers import ProfessorSerializer
from professors.models import (
    Professor,
    ProfessorAddress,
    ProfessorExperience,
    ProfessorQualification,
    professorAdminEmployement,
    professorClassAssigned,
)
from published_professors.models import PublishedProfessor
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
from subordinate_access.models import SubordinateAccess
from syllabus.models import AcademicTerms, Branch, Course, Subject
from django.utils import timezone


CLASS_NAME = 'B.A'
BRANCH_NAME = 'History'
ACADEMIC_TERM = '1st Semester'
ACADEMIC_YEAR = '2025-2026'
DEFAULT_PROFESSOR_COUNT = 3
DEFAULT_STUDENT_COUNT = 3
DEFAULT_ATTENDANCE_DAYS = 365
TOTAL_FEE_AMOUNT = 36000
OPENING_TIME = time(8, 0)
ADMIN_ACCESS_CODE = 'DEMO-ADMIN-YEAR-ACCESS'
FEE_ACCESS_CODE = 'DEMO-FEE-YEAR-ACCESS'
ADMIN_EMPLOYEE_NAME = 'Demo Admin Employee'
FEE_EMPLOYEE_NAME = 'Demo Fee Employee'

CHECKIN_OFFSETS_MINUTES = [-8, -5, -3, -1, 0, 2, 4, 6, 9, -6, 5, 11]

PROFESSOR_PROFILES = [
    {
        'name': 'Dr Nandita Roy',
        'father_name': 'Sudhir Roy',
        'mother_name': 'Mita Roy',
        'gender': 'Female',
        'designation': 'Assistant Professor',
        'subject': 'History of India',
        'interest': 'Modern Indian History',
    },
    {
        'name': 'Dr Arindam Sen',
        'father_name': 'Subhash Sen',
        'mother_name': 'Mala Sen',
        'gender': 'Male',
        'designation': 'Associate Professor',
        'subject': 'World History',
        'interest': 'European Political History',
    },
    {
        'name': 'Dr Poulomi Das',
        'father_name': 'Tapan Das',
        'mother_name': 'Anjana Das',
        'gender': 'Female',
        'designation': 'Assistant Professor',
        'subject': 'Ancient Civilizations',
        'interest': 'Social and Cultural History',
    },
]

STUDENT_NAMES = [
    'Aarav Sharma',
    'Diya Singh',
    'Kabir Verma',
]

SEMESTER_SUBJECTS = [
    'History of India',
    'World History',
    'Ancient Civilizations',
    'Historical Methods',
    'Political Theory',
]

LEAVE_REASONS = [
    'Medical leave',
    'Family function',
    'Academic workshop',
    'Personal work',
]


class Command(BaseCommand):
    help = (
        'Create dummy History professors with year-long attendance, monthly payments, '
        'and B.A History 1st Semester students with timed daily attendance submissions.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--institute-id',
            type=int,
            help='Institute ID to attach the dummy data to. Defaults to the first active institute.',
        )
        parser.add_argument(
            '--professor-count',
            type=int,
            default=DEFAULT_PROFESSOR_COUNT,
            help='Number of professors to create. Defaults to 3.',
        )
        parser.add_argument(
            '--student-count',
            type=int,
            default=DEFAULT_STUDENT_COUNT,
            help='Number of students to create. Defaults to 3.',
        )
        parser.add_argument(
            '--attendance-days',
            type=int,
            default=DEFAULT_ATTENDANCE_DAYS,
            help='Number of attendance days to generate. Defaults to 365.',
        )
        parser.add_argument(
            '--branch-name',
            default=BRANCH_NAME,
            help='Branch name to use for the demo. Defaults to History.',
        )

    def _get_institute(self, institute_id):
        if institute_id is not None:
            try:
                return Institute.objects.get(pk=institute_id)
            except Institute.DoesNotExist as exc:
                raise CommandError(f'Institute with id={institute_id} was not found.') from exc

        institute = Institute.objects.filter(event_status='active').order_by('id').first()
        if institute is None:
            institute = Institute.objects.order_by('id').first()

        if institute is None:
            raise CommandError('No institute found. Create an institute before seeding this demo data.')

        return institute

    def _get_date_range(self, attendance_days):
        last_day = date.today()
        first_day = last_day - timedelta(days=attendance_days - 1)
        return first_day, last_day

    def _build_mobile_number(self, seed_number, prefix='9'):
        return f'{prefix}{800000000 + seed_number:09d}'

    def _build_checkin_time(self, entity_offset, day_offset):
        offset_minutes = CHECKIN_OFFSETS_MINUTES[
            (entity_offset + day_offset) % len(CHECKIN_OFFSETS_MINUTES)
        ]
        total_minutes = (OPENING_TIME.hour * 60) + OPENING_TIME.minute + offset_minutes
        hour, minute = divmod(total_minutes, 60)
        return time(hour=hour, minute=minute)

    def _aware_datetime(self, date_value, time_value):
        return timezone.make_aware(
            datetime.combine(date_value, time_value),
            timezone.get_current_timezone(),
        )

    def _next_working_day(self, date_value, last_day):
        resolved_date = min(date_value, last_day)
        if resolved_date.weekday() == 6 and resolved_date < last_day:
            return resolved_date + timedelta(days=1)
        return resolved_date

    def _ensure_subordinate_access(self, institute, *, name, post, access_control, access_code):
        subordinate = (
            SubordinateAccess.objects
            .filter(institute=institute, access_code=access_code)
            .order_by('id')
            .first()
        )
        defaults = {
            'name': name,
            'post': post,
            'access_control': access_control,
            'is_active': True,
        }

        if subordinate is None:
            return SubordinateAccess.objects.create(
                institute=institute,
                access_code=access_code,
                **defaults,
            )

        changed_fields = []
        for field_name, value in defaults.items():
            if getattr(subordinate, field_name) != value:
                setattr(subordinate, field_name, value)
                changed_fields.append(field_name)

        if changed_fields:
            subordinate.save(update_fields=changed_fields)

        return subordinate

    def _ensure_dummy_staff(self, institute):
        admin_employee = self._ensure_subordinate_access(
            institute,
            name=ADMIN_EMPLOYEE_NAME,
            post='Admin Employee',
            access_control=ADMIN_ACCESS_CONTROL,
            access_code=ADMIN_ACCESS_CODE,
        )
        fee_employee = self._ensure_subordinate_access(
            institute,
            name=FEE_EMPLOYEE_NAME,
            post='Fee Employee',
            access_control=FEE_ACCESS_CONTROL,
            access_code=FEE_ACCESS_CODE,
        )
        return admin_employee, fee_employee

    def _actor_snapshot(self, subordinate):
        return {
            'actor_name': subordinate.name,
            'actor_role': subordinate.post,
            'actor_access_control': subordinate.access_control,
            'actor_source': 'subordinate_access',
        }

    def _month_start(self, value):
        return value.replace(day=1)

    def _next_month_start(self, value):
        if value.month == 12:
            return value.replace(year=value.year + 1, month=1, day=1)
        return value.replace(month=value.month + 1, day=1)

    def _month_end(self, value):
        return self._next_month_start(value) - timedelta(days=1)

    def _payment_month_starts(self, attendance_days):
        _first_day, last_day = self._get_date_range(attendance_days)
        month_count = max(1, math.ceil(attendance_days / 30.44))
        current = self._month_start(last_day)
        months = []

        for _ in range(month_count):
            months.append(current)
            if current.month == 1:
                current = current.replace(year=current.year - 1, month=12, day=1)
            else:
                current = current.replace(month=current.month - 1, day=1)

        months.reverse()
        return months, last_day

    def _ensure_academic_structure(self, institute):
        course = (
            Course.objects
            .filter(institute=institute, name=self.class_name)
            .order_by('id')
            .first()
        )
        if course is None:
            course = Course.objects.create(
                institute=institute,
                name=self.class_name,
            )

        branch = (
            Branch.objects
            .filter(course=course, name=self.branch_name)
            .order_by('id')
            .first()
        )
        if branch is None:
            branch = Branch.objects.create(
                course=course,
                name=self.branch_name,
            )

        academic_term = (
            AcademicTerms.objects
            .filter(branch=branch, name=self.academic_term)
            .order_by('id')
            .first()
        )
        if academic_term is None:
            academic_term = AcademicTerms.objects.create(
                branch=branch,
                name=self.academic_term,
            )

        for unit_number, subject_name in enumerate(SEMESTER_SUBJECTS, start=1):
            subject = (
                Subject.objects
                .filter(academic_terms=academic_term, name=subject_name)
                .order_by('id')
                .first()
            )
            if subject is None:
                Subject.objects.create(
                    academic_terms=academic_term,
                    name=subject_name,
                    unit=unit_number,
                )

        return academic_term

    def _create_professors(self, institute, professor_count):
        starting_index = (
            Professor.objects.order_by('-id').values_list('id', flat=True).first() or 0
        ) + 1

        professors = []
        for offset in range(professor_count):
            seed_number = starting_index + offset
            profile = PROFESSOR_PROFILES[offset % len(PROFESSOR_PROFILES)]

            professor = Professor.objects.create(
                institute=institute,
                name=f"{profile['name']} {seed_number:03d}",
                father_name=profile['father_name'],
                mother_name=profile['mother_name'],
                date_of_birth=date(1983 + (offset % 7), ((offset + 2) % 12) + 1, 10 + (offset % 9)),
                gender=profile['gender'],
                phone_number=self._build_mobile_number(seed_number, prefix='8'),
                email=f'ba.history.prof{seed_number:04d}@dummy.local',
                indentity_number=f'HISTPROF{seed_number:06d}',
                marital_status='Married' if offset % 2 else 'Single',
            )

            ProfessorAddress.objects.create(
                professor=professor,
                current_address=f'History Faculty Quarter {seed_number}, Kolkata',
                permanent_address=f'History Faculty Quarter {seed_number}, Kolkata',
                city='Kolkata',
                state='West Bengal',
                country='India',
            )
            ProfessorQualification.objects.create(
                professor=professor,
                degree='M.A',
                institution='Dummy University',
                year_of_passing=str(2006 + (offset % 8)),
                percentage=str(72 + (offset % 9)),
                specialization='History',
            )
            ProfessorExperience.objects.create(
                professor=professor,
                designation=profile['designation'],
                department=self.branch_name,
                teaching_subject=profile['subject'],
                teaching_experience=str(4 + offset),
                interest=profile['interest'],
            )
            professorAdminEmployement.objects.create(
                professor=professor,
                personal_id=f'HISTPID{seed_number:05d}',
                employee_id=f'HISTEMP{seed_number:05d}',
                date_of_joining=date(2018 + (offset % 4), 7, 1 + offset),
                employement_type='Full Time',
                working_hours='8',
                salary=str(42000 + (offset * 3500)),
            )
            professorClassAssigned.objects.create(
                professor=professor,
                assigned_course=self.class_name,
                assigned_section=self.branch_name,
                assigned_year=self.academic_term,
                session=self.academic_year,
            )

            professors.append(professor)

        return professors

    def _sync_published_professors(self, institute, professors):
        published_professors = []
        now = timezone.now()

        for professor in professors:
            professor_data = ProfessorSerializer(professor).data
            personal_id = (
                (professor_data.get('admin_employement') or {}).get('personal_id', '')
            )

            published_professor, _ = PublishedProfessor.objects.update_or_create(
                institute=institute,
                source_professor_id=professor.id,
                defaults={
                    'name': professor.name,
                    'email': professor.email,
                    'professor_personal_id': personal_id,
                    'professor_data': professor_data,
                    'published_at': now,
                    'updated_at': now,
                },
            )
            published_professors.append(published_professor)

        return published_professors

    def _create_professor_attendance(self, institute, professors, attendance_days):
        first_day, _ = self._get_date_range(attendance_days)
        total_rows = 0

        for professor_offset, professor in enumerate(professors):
            rows = []
            for day_offset in range(attendance_days):
                current_date = first_day + timedelta(days=day_offset)
                if current_date.weekday() == 6:
                    continue

                is_present = (day_offset + professor_offset) % 17 != 0
                rows.append(
                    ProfessorAttendance(
                        institute=institute,
                        professor=professor,
                        date=current_date,
                        status=is_present,
                        attendance_time=self._build_checkin_time(professor_offset, day_offset),
                    )
                )

            ProfessorAttendance.objects.bulk_create(rows)
            total_rows += len(rows)

        return total_rows

    def _create_professor_payments(self, institute, professors, attendance_days):
        month_starts, last_day = self._payment_month_starts(attendance_days)
        rows = []

        for professor in professors:
            raw_salary = getattr(professor.admin_employement, 'salary', '') or '0'
            try:
                payment_amount = int(float(raw_salary))
            except (TypeError, ValueError):
                payment_amount = 0

            for month_start in month_starts:
                month_end = self._month_end(month_start)
                rows.append(
                    ProfessorsPayments(
                        institute=institute,
                        professor=professor,
                        month_year=month_start.strftime('%Y-%m'),
                        payment_date=min(month_end, last_day),
                        payment_amount=payment_amount,
                        payment_status='paid',
                    )
                )

        ProfessorsPayments.objects.bulk_create(rows)
        return len(rows)

    def _create_professor_leaves(self, institute, professors, published_professors, attendance_days):
        first_day, last_day = self._get_date_range(attendance_days)
        InstituteTotalLeave.objects.update_or_create(
            institute=institute,
            defaults={
                'total_leaves': 24,
                'session_start_month': 4,
                'session_end_month': 3,
                'opening_time': OPENING_TIME,
                'closing_time': time(17, 0),
            },
        )

        statuses = [
            PublishedProfessorLeave.LeaveStatus.ACCEPTED,
            PublishedProfessorLeave.LeaveStatus.ACCEPTED,
            PublishedProfessorLeave.LeaveStatus.CANCELLED,
            PublishedProfessorLeave.LeaveStatus.PENDING,
        ]
        leaves = []

        for professor_offset, (professor, published_professor) in enumerate(
            zip(professors, published_professors)
        ):
            leave_offsets = [
                24 + professor_offset * 3,
                112 + professor_offset * 5,
                202 + professor_offset * 7,
                292 + professor_offset * 2,
            ]
            experience = getattr(professor, 'experience', None)

            for leave_index, leave_offset in enumerate(leave_offsets):
                if leave_offset >= attendance_days:
                    continue

                start_date = self._next_working_day(
                    first_day + timedelta(days=leave_offset),
                    last_day,
                )
                end_date = min(
                    start_date + timedelta(days=leave_index % 2),
                    last_day,
                )
                leave_status = statuses[(leave_index + professor_offset) % len(statuses)]
                cancellation_reason = (
                    'Class coverage was arranged by the department.'
                    if leave_status == PublishedProfessorLeave.LeaveStatus.CANCELLED
                    else ''
                )

                leave = PublishedProfessorLeave.objects.create(
                    institute=institute,
                    published_professor=published_professor,
                    professor_name=professor.name,
                    department=getattr(experience, 'department', self.branch_name),
                    email=professor.email,
                    start_date=start_date,
                    end_date=end_date,
                    current_time=time(10, min(55, 10 + professor_offset + leave_index)),
                    reason=LEAVE_REASONS[leave_index % len(LEAVE_REASONS)],
                    leaves_status=leave_status,
                    cancellation_reason=cancellation_reason,
                )
                leaves.append(leave)

                if leave_status == PublishedProfessorLeave.LeaveStatus.ACCEPTED:
                    ProfessorAttendance.objects.filter(
                        institute=institute,
                        professor=professor,
                        date__range=(start_date, end_date),
                    ).update(status=False)

        return leaves

    def _create_students(self, institute, student_count, start_class_date):
        starting_index = (
            Student.objects.order_by('-id').values_list('id', flat=True).first() or 0
        ) + 1

        students = []
        for offset in range(student_count):
            seed_number = starting_index + offset
            student_name = STUDENT_NAMES[offset % len(STUDENT_NAMES)]
            student = Student.objects.create(
                institute=institute,
                name=f'{student_name} {seed_number:03d}',
                dob=date(2006, ((offset + 5) % 12) + 1, 12 + offset),
                gender='Female' if offset % 2 else 'Male',
                nationality='Indian',
                identity=f'BAHISTSTD{seed_number:06d}',
                category='General' if offset % 2 == 0 else 'OBC',
            )

            StudentContactDetails.objects.create(
                student=student,
                email=f'ba.history.student{seed_number:04d}@dummy.local',
                permanent_address=f'History Student Lane {seed_number}, Kolkata',
                current_address=f'History Student Lane {seed_number}, Kolkata',
                mobile=self._build_mobile_number(seed_number),
                father_name=f'Parent {seed_number:03d}',
                mother_name=f'Mother {seed_number:03d}',
                guardian_name=f'Guardian {seed_number:03d}',
                parent_contact=self._build_mobile_number(seed_number + 5000),
            )
            StudentEducationDetails.objects.create(
                student=student,
                qualification='12th Pass',
                passing_year=2025,
                institute_name='Dummy Higher Secondary School',
                marks_obtained='81%',
            )
            StudentAdmissionDetails.objects.create(
                student=student,
                enrollment_number=f'BAHISTENR{seed_number:04d}',
                roll_number=f'BAHISTROL{seed_number:04d}',
                admission_date=start_class_date - timedelta(days=10),
                start_class_date=start_class_date,
                academic_year=self.academic_year,
            )
            StudentCourseAssignment.objects.create(
                student=student,
                class_name=self.class_name,
                branch=self.branch_name,
                academic_term=self.academic_term,
            )
            StudentFeeDetails.objects.create(
                student=student,
                total_fee_amount=TOTAL_FEE_AMOUNT,
                paid_amount=TOTAL_FEE_AMOUNT,
                pending_amount=0,
            )
            StudentSystemDetails.objects.create(
                student=student,
                student_personal_id=f'HISTSTD{seed_number:06d}',
                library_card_number=f'HISTLIB{seed_number:06d}',
                hostel_details='Day Scholar',
                verification_status='verified',
            )

            SubjectsAssigned.objects.bulk_create([
                SubjectsAssigned(student=student, subject=subject, unit=str(unit_number))
                for unit_number, subject in enumerate(SEMESTER_SUBJECTS, start=1)
            ])

            students.append(student)

        return students

    def _create_student_attendance(self, institute, students, professors, attendance_days):
        first_day, _ = self._get_date_range(attendance_days)
        total_rows = 0
        current_timezone = timezone.get_current_timezone()

        for day_offset in range(attendance_days):
            current_date = first_day + timedelta(days=day_offset)
            if current_date.weekday() == 6:
                continue

            marked_by = professors[day_offset % len(professors)]
            attendance_time = self._build_checkin_time(len(professors), day_offset)
            submitted_at = timezone.make_aware(
                datetime.combine(current_date, attendance_time),
                current_timezone,
            )
            submission = AttendanceSubmission.objects.create(
                institute=institute,
                date=current_date,
                class_name=self.class_name,
                branch=self.branch_name,
                year_semester=self.academic_term,
                marked_by=marked_by,
                submitted_at=submitted_at,
                attendance_time=attendance_time,
            )

            rows = [
                Attendance(
                    student=student,
                    submission=submission,
                    status=(day_offset + (student_offset * 2)) % 11 != 0,
                )
                for student_offset, student in enumerate(students)
            ]

            Attendance.objects.bulk_create(rows)
            total_rows += len(rows)

        return total_rows

    def _build_admin_attendance_events(self, institute, admin_employee, professors, attendance_days):
        first_day, _ = self._get_date_range(attendance_days)
        professor_ids = [professor.id for professor in professors]
        attendance_by_date = {}

        attendance_records = (
            ProfessorAttendance.objects
            .filter(
                institute=institute,
                professor_id__in=professor_ids,
                date__gte=first_day,
            )
            .select_related('professor')
            .order_by('date', 'professor_id')
        )

        for record in attendance_records:
            bucket = attendance_by_date.setdefault(
                record.date,
                {
                    'present_count': 0,
                    'absent_count': 0,
                    'absent_professors': [],
                    'professor_ids': [],
                },
            )
            bucket['professor_ids'].append(record.professor_id)
            if record.status:
                bucket['present_count'] += 1
            else:
                bucket['absent_count'] += 1
                bucket['absent_professors'].append(record.professor.name)

        actor = self._actor_snapshot(admin_employee)
        events = []
        for current_date, summary in sorted(attendance_by_date.items()):
            professor_count = len(summary['professor_ids'])
            events.append(
                ActivityEvent(
                    institute=institute,
                    **actor,
                    action='mark',
                    entity_type='professor attendance',
                    entity_name=f'{self.class_name} {self.branch_name} faculty',
                    title='Admin employee recorded professor attendance',
                    description=(
                        f"{summary['present_count']} present and "
                        f"{summary['absent_count']} absent out of {professor_count} professors."
                    ),
                    details={
                        'task': 'take_professor_attendance',
                        'date': current_date.isoformat(),
                        'class_name': self.class_name,
                        'branch': self.branch_name,
                        'academic_term': self.academic_term,
                        'professor_count': professor_count,
                        'present_count': summary['present_count'],
                        'absent_count': summary['absent_count'],
                        'absent_professors': summary['absent_professors'],
                        'professor_ids': summary['professor_ids'],
                    },
                    occurred_at=self._aware_datetime(current_date, time(8, 35)),
                )
            )

        return events

    def _build_admin_payment_events(self, institute, admin_employee, professors):
        professor_ids = [professor.id for professor in professors]
        payments_by_month = {}
        payments = (
            ProfessorsPayments.objects
            .filter(institute=institute, professor_id__in=professor_ids)
            .select_related('professor')
            .order_by('month_year', 'professor_id')
        )

        for payment in payments:
            bucket = payments_by_month.setdefault(
                payment.month_year,
                {
                    'payment_date': payment.payment_date,
                    'payment_count': 0,
                    'total_amount': 0,
                    'payments': [],
                },
            )
            bucket['payment_count'] += 1
            bucket['total_amount'] += payment.payment_amount
            bucket['payment_date'] = max(bucket['payment_date'], payment.payment_date)
            bucket['payments'].append({
                'professor_id': payment.professor_id,
                'professor_name': payment.professor.name if payment.professor else '',
                'amount': payment.payment_amount,
                'status': payment.payment_status,
            })

        actor = self._actor_snapshot(admin_employee)
        events = []
        for month_year, summary in sorted(payments_by_month.items()):
            payment_date = summary['payment_date'] or date.fromisoformat(f'{month_year}-01')
            events.append(
                ActivityEvent(
                    institute=institute,
                    **actor,
                    action='mark',
                    entity_type='professor payment',
                    entity_name=f'{month_year} professor salaries',
                    title='Admin employee recorded professor salary payments',
                    description=(
                        f"Recorded {summary['payment_count']} professor payments "
                        f"for {month_year}."
                    ),
                    details={
                        'task': 'professor_salary_payment',
                        'month_year': month_year,
                        'payment_count': summary['payment_count'],
                        'total_amount': summary['total_amount'],
                        'payments': summary['payments'],
                    },
                    occurred_at=self._aware_datetime(payment_date, time(14, 30)),
                )
            )

        return events

    def _build_admin_leave_events(self, institute, admin_employee, leaves):
        actor = self._actor_snapshot(admin_employee)
        events = []

        for leave_index, leave in enumerate(leaves):
            events.append(
                ActivityEvent(
                    institute=institute,
                    **actor,
                    action='review',
                    entity_type='professor leave',
                    entity_id=leave.id,
                    entity_name=leave.professor_name,
                    title='Admin employee reviewed professor leave',
                    description=(
                        f"{leave.professor_name} leave from {leave.start_date} "
                        f"to {leave.end_date} is {leave.leaves_status}."
                    ),
                    details={
                        'task': 'manage_professor_leave',
                        'professor_id': leave.published_professor.source_professor_id,
                        'published_professor_id': leave.published_professor_id,
                        'professor_name': leave.professor_name,
                        'department': leave.department,
                        'start_date': leave.start_date.isoformat(),
                        'end_date': leave.end_date.isoformat(),
                        'total_days': leave.total_days,
                        'reason': leave.reason,
                        'leaves_status': leave.leaves_status,
                        'cancellation_reason': leave.cancellation_reason,
                    },
                    occurred_at=self._aware_datetime(
                        leave.start_date,
                        time(11, min(55, 5 + leave_index)),
                    ),
                )
            )

        return events

    def _build_fee_employee_events(self, institute, fee_employee, students, attendance_days):
        first_day, last_day = self._get_date_range(attendance_days)
        actor = self._actor_snapshot(fee_employee)
        events = []

        month_starts, _ = self._payment_month_starts(attendance_days)
        total_fee_amount = TOTAL_FEE_AMOUNT * len(students)
        for month_start in month_starts:
            activity_date = self._next_working_day(
                max(first_day, month_start + timedelta(days=4)),
                last_day,
            )
            events.append(
                ActivityEvent(
                    institute=institute,
                    **actor,
                    action='review',
                    entity_type='student fee',
                    entity_name=f'{month_start.strftime("%Y-%m")} fee ledger',
                    title='Fee employee reviewed student fee ledger',
                    description=(
                        f"Reviewed fee ledger for {len(students)} students in "
                        f"{month_start.strftime('%Y-%m')}."
                    ),
                    details={
                        'task': 'student_fee_ledger_review',
                        'month_year': month_start.strftime('%Y-%m'),
                        'student_count': len(students),
                        'class_name': self.class_name,
                        'branch': self.branch_name,
                        'academic_term': self.academic_term,
                        'total_fee_amount': total_fee_amount,
                    },
                    occurred_at=self._aware_datetime(activity_date, time(12, 5)),
                )
            )

        installment_count = 4
        for student_offset, student in enumerate(students):
            fee_details = getattr(student, 'fee_details', None)
            student_total_fee = int(
                getattr(fee_details, 'total_fee_amount', TOTAL_FEE_AMOUNT)
                or TOTAL_FEE_AMOUNT
            )
            base_installment = student_total_fee // installment_count
            paid_amount = 0

            for installment_index in range(installment_count):
                is_last_installment = installment_index == installment_count - 1
                payment_amount = (
                    student_total_fee - paid_amount
                    if is_last_installment
                    else base_installment
                )
                paid_amount += payment_amount
                pending_amount = max(student_total_fee - paid_amount, 0)
                base_offset = int(
                    ((attendance_days - 1) * (installment_index + 1)) / installment_count
                )
                activity_date = self._next_working_day(
                    first_day + timedelta(days=min(attendance_days - 1, base_offset + student_offset)),
                    last_day,
                )

                events.append(
                    ActivityEvent(
                        institute=institute,
                        **actor,
                        action='update',
                        entity_type='student fee',
                        entity_id=student.id,
                        entity_name=student.name,
                        title='Fee employee updated student fee',
                        description=(
                            f"Collected installment {installment_index + 1} "
                            f"from {student.name}."
                        ),
                        details={
                            'task': 'student_fee_collection',
                            'student_id': student.id,
                            'student_name': student.name,
                            'class_name': self.class_name,
                            'branch': self.branch_name,
                            'academic_term': self.academic_term,
                            'academic_year': self.academic_year,
                            'installment': installment_index + 1,
                            'installments': installment_count,
                            'payment_amount': payment_amount,
                            'total_fee_amount': student_total_fee,
                            'paid_amount': paid_amount,
                            'pending_amount': pending_amount,
                        },
                        occurred_at=self._aware_datetime(
                            activity_date,
                            time(12, min(55, 20 + student_offset)),
                        ),
                    )
                )

        return events

    def _create_yearly_activity_feed(
        self,
        institute,
        admin_employee,
        fee_employee,
        professors,
        students,
        leaves,
        attendance_days,
    ):
        events = []
        events.extend(
            self._build_admin_attendance_events(
                institute,
                admin_employee,
                professors,
                attendance_days,
            )
        )
        events.extend(self._build_admin_payment_events(institute, admin_employee, professors))
        events.extend(self._build_admin_leave_events(institute, admin_employee, leaves))
        events.extend(
            self._build_fee_employee_events(
                institute,
                fee_employee,
                students,
                attendance_days,
            )
        )

        ActivityEvent.objects.bulk_create(events, batch_size=500)
        return len(events)

    def handle(self, *args, **options):
        professor_count = options['professor_count']
        student_count = options['student_count']
        attendance_days = options['attendance_days']
        self.class_name = CLASS_NAME
        self.branch_name = (options.get('branch_name') or BRANCH_NAME).strip()
        self.academic_term = ACADEMIC_TERM
        self.academic_year = ACADEMIC_YEAR

        if professor_count <= 0:
            raise CommandError('--professor-count must be greater than 0.')
        if student_count <= 0:
            raise CommandError('--student-count must be greater than 0.')
        if attendance_days <= 0:
            raise CommandError('--attendance-days must be greater than 0.')
        if not self.branch_name:
            raise CommandError('--branch-name must not be blank.')
        if len(self.branch_name) > 20:
            raise CommandError('--branch-name must be 20 characters or fewer.')

        institute = self._get_institute(options.get('institute_id'))
        start_class_date, _ = self._get_date_range(attendance_days)

        with transaction.atomic():
            self._ensure_academic_structure(institute)
            admin_employee, fee_employee = self._ensure_dummy_staff(institute)
            professors = self._create_professors(institute, professor_count)
            published_professors = self._sync_published_professors(institute, professors)
            professor_attendance_count = self._create_professor_attendance(
                institute,
                professors,
                attendance_days,
            )
            professor_payment_count = self._create_professor_payments(
                institute,
                professors,
                attendance_days,
            )
            professor_leave_count = len(
                self._create_professor_leaves(
                    institute,
                    professors,
                    published_professors,
                    attendance_days,
                )
            )
            students = self._create_students(institute, student_count, start_class_date)
            student_attendance_count = self._create_student_attendance(
                institute,
                students,
                professors,
                attendance_days,
            )
            activity_event_count = self._create_yearly_activity_feed(
                institute,
                admin_employee,
                fee_employee,
                professors,
                students,
                list(
                    PublishedProfessorLeave.objects.filter(
                        institute=institute,
                        published_professor__in=published_professors,
                    ).order_by('start_date', 'id')
                ),
                attendance_days,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Created {len(professors)} dummy professors and {len(students)} dummy students '
                f'for {self.class_name} / {self.branch_name} / {self.academic_term} in institute '
                f'"{institute.name}" (id={institute.id}). '
                f'Synced {len(published_professors)} published professor snapshots. '
                f'Created {professor_attendance_count} professor attendance rows with check-in times, '
                f'{professor_payment_count} professor payment rows, {professor_leave_count} '
                f'professor leave rows, and {student_attendance_count} '
                f'student attendance rows with daily submission times around '
                f'{OPENING_TIME.strftime("%I:%M %p")}. Added {activity_event_count} '
                f'activity feed events for admin and fee employee work.'
            )
        )
