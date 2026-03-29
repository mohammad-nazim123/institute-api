from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iinstitutes_list.models import Institute
from professors.models import (
    Professor,
    ProfessorAddress,
    ProfessorExperience,
    ProfessorQualification,
    professorAdminEmployement,
    professorClassAssigned,
)


DEPARTMENTS = [
    'CSE',
    'ECE',
    'ME',
    'CE',
    'EEE',
]

DESIGNATIONS = [
    'Assistant Professor',
    'Associate Professor',
    'Professor',
]

COURSES = [
    'B.Tech',
    'B.Sc',
    'M.Tech',
]

SECTIONS = ['A', 'B', 'C']
MARITAL_STATUSES = ['Single', 'Married']
GENDERS = ['Male', 'Female']


class Command(BaseCommand):
    help = 'Create dummy professors for an institute without sending any emails.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Number of dummy professors to create. Defaults to 50.',
        )
        parser.add_argument(
            '--institute-id',
            type=int,
            help='Institute ID to attach the dummy professors to. Defaults to the first institute.',
        )

    def _get_institute(self, institute_id):
        if institute_id is not None:
            try:
                return Institute.objects.get(pk=institute_id)
            except Institute.DoesNotExist as exc:
                raise CommandError(f'Institute with id={institute_id} was not found.') from exc

        institute = Institute.objects.order_by('id').first()
        if institute is None:
            raise CommandError('No institute found. Create an institute before seeding professors.')
        return institute

    def handle(self, *args, **options):
        count = options['count']
        if count <= 0:
            raise CommandError('--count must be greater than 0.')

        institute = self._get_institute(options.get('institute_id'))
        starting_index = (Professor.objects.order_by('-id').values_list('id', flat=True).first() or 0) + 1

        created_ids = []

        with transaction.atomic():
            for offset in range(count):
                seed_number = starting_index + offset
                professor = Professor.objects.create(
                    institute=institute,
                    name=f'Professor {seed_number:03d}',
                    father_name=f'Father {seed_number:03d}',
                    mother_name=f'Mother {seed_number:03d}',
                    date_of_birth=date(1980 + (seed_number % 15), ((seed_number % 12) + 1), ((seed_number % 28) + 1)),
                    gender=GENDERS[offset % len(GENDERS)],
                    phone_number=f'90000{seed_number:05d}',
                    email='',
                    indentity_number=f'ID{seed_number:06d}',
                    marital_status=MARITAL_STATUSES[offset % len(MARITAL_STATUSES)],
                )
                created_ids.append(professor.id)

                ProfessorAddress.objects.create(
                    professor=professor,
                    current_address=f'Current Address {seed_number}',
                    permanent_address=f'Permanent Address {seed_number}',
                    city='Kolkata',
                    state='West Bengal',
                    country='India',
                )
                ProfessorQualification.objects.create(
                    professor=professor,
                    degree='M.Tech',
                    institution='Dummy University',
                    year_of_passing=str(2005 + (seed_number % 15)),
                    percentage=str(70 + (seed_number % 20)),
                    specialization=DEPARTMENTS[offset % len(DEPARTMENTS)],
                )
                ProfessorExperience.objects.create(
                    professor=professor,
                    designation=DESIGNATIONS[offset % len(DESIGNATIONS)],
                    department=DEPARTMENTS[offset % len(DEPARTMENTS)],
                    teaching_subject=f'Subject {seed_number:03d}',
                    teaching_experience=str(1 + (seed_number % 15)),
                    interest=f'Interest {seed_number:03d}',
                )
                professorAdminEmployement.objects.create(
                    professor=professor,
                    personal_id=f'PID{seed_number:06d}',
                    employee_id=f'EMP{seed_number:06d}',
                    date_of_joining=date(2010 + (seed_number % 10), ((seed_number % 12) + 1), ((seed_number % 28) + 1)),
                    employement_type='Full Time',
                    working_hours='8',
                    salary=str(30000 + (seed_number * 100)),
                )
                professorClassAssigned.objects.create(
                    professor=professor,
                    assigned_course=COURSES[offset % len(COURSES)],
                    assigned_section=SECTIONS[offset % len(SECTIONS)],
                    assigned_year=str(1 + (seed_number % 4)),
                    session='2025-2026',
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Created {count} dummy professors for institute "{institute.name}" (id={institute.id}). '
                'All dummy professors were created with blank email fields.'
            )
        )
