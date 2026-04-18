from datetime import date, datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from activity_feed.models import ActivityEvent
from attendance.models import Attendance, AttendanceSubmission
from default_activities.models import DefaultActivity
from iinstitutes_list.models import Institute
from professor_attendance.models import ProfessorAttendance
from professor_leaves.models import ProfessorLeave
from professors.models import Professor, ProfessorExperience, professorAdminEmployement
from published_professors.models import PublishedProfessor
from students.models import Student
from subordinate_access.models import SubordinateAccess


class TimingAnalysisBulkApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Timing Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.url = reverse('data-analysis-timing-analysis')
        self.current_timezone = timezone.get_current_timezone()
        DefaultActivity.objects.create(
            institute=self.institute,
            session_month='Jan-Dec',
            session_year='2026-2027',
            academic_terms_type='semester',
            opening_time='08:00',
            closing_time='17:00',
            total_yearly_leaves=12,
        )
        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Timing',
            email='timing@example.com',
            phone_number='9999999999',
        )
        ProfessorExperience.objects.create(
            professor=self.professor,
            department='CSE',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='TIMINGPROF00001',
            employee_id='EMP-TIME',
        )
        SubordinateAccess.objects.create(
            institute=self.institute,
            post='Manager',
            name='Nina',
            access_control='admin access',
            access_code='n' * 32,
            is_active=True,
        )
        ActivityEvent.objects.create(
            institute=self.institute,
            actor_name='Admin',
            actor_role='Super Admin',
            actor_access_control='full access',
            actor_source='super_admin',
            action='create',
            entity_type='payment request',
            entity_name='Payment April',
            title='Payment created',
            description='',
            details={},
            occurred_at=timezone.make_aware(
                datetime.combine(date(2026, 4, 5), time(9, 0)),
                self.current_timezone,
            ),
        )
        ActivityEvent.objects.create(
            institute=self.institute,
            actor_name='Admin',
            actor_role='Super Admin',
            actor_access_control='full access',
            actor_source='super_admin',
            action='create',
            entity_type='payment request',
            entity_name='Payment Old',
            title='Payment old',
            description='',
            details={},
            occurred_at=timezone.make_aware(
                datetime.combine(date(2025, 12, 30), time(9, 0)),
                self.current_timezone,
            ),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 4, 5),
            status=True,
            attendance_time=time(8, 10),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 5, 5),
            status=True,
            attendance_time=time(8, 15),
        )
        self.student = Student.objects.create(
            institute=self.institute,
            name='Student Timing',
        )
        april_submission = AttendanceSubmission.objects.create(
            institute=self.institute,
            date=date(2026, 4, 5),
            class_name='BA',
            branch='History',
            year_semester='1st Semester',
            marked_by=self.professor,
            submitted_at=timezone.make_aware(
                datetime.combine(date(2026, 4, 5), time(9, 30)),
                self.current_timezone,
            ),
        )
        may_submission = AttendanceSubmission.objects.create(
            institute=self.institute,
            date=date(2026, 5, 5),
            class_name='BA',
            branch='History',
            year_semester='1st Semester',
            marked_by=self.professor,
            submitted_at=timezone.make_aware(
                datetime.combine(date(2026, 5, 5), time(9, 45)),
                self.current_timezone,
            ),
        )
        Attendance.objects.create(
            student=self.student,
            submission=april_submission,
            status=True,
        )
        Attendance.objects.create(
            student=Student.objects.create(
                institute=self.institute,
                name='Student Timing May',
            ),
            submission=may_submission,
            status=False,
        )

    def test_timing_analysis_requires_authenticated_admin_access(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&year=2026'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_timing_analysis_returns_selected_year_and_excludes_access_code(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&year=2026',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['year'], 2026)
        self.assertEqual(response.data['timeline_count'], 1)
        self.assertEqual(len(response.data['timeline']), 1)
        self.assertEqual(response.data['timeline'][0]['title'], 'Payment created')
        self.assertEqual(len(response.data['subordinates']), 1)
        self.assertNotIn('access_code', response.data['subordinates'][0])
        self.assertNotIn('professor_attendance', response.data)
        self.assertNotIn('student_attendance', response.data)
        self.assertEqual(response.data['default_activity']['total_yearly_leaves'], 12)
        self.assertEqual(
            response.data['professors'][0]['admin_employement']['employee_id'],
            'EMP-TIME',
        )

    def test_timing_analysis_monthly_bulk_returns_month_records(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&year=2026&month=2026-04',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['year'], 2026)
        self.assertEqual(response.data['month'], '2026-04')
        self.assertEqual(response.data['default_activity']['opening_time'], '08:00 AM')
        self.assertEqual(len(response.data['professors']), 1)
        self.assertEqual(len(response.data['subordinates']), 1)
        self.assertEqual(response.data['timeline_count'], 1)
        self.assertEqual(response.data['timeline'][0]['title'], 'Payment created')
        self.assertEqual(response.data['professor_attendance_count'], 1)
        self.assertEqual(response.data['student_attendance_count'], 1)
        self.assertEqual(
            response.data['professor_attendance'][0]['date'],
            '2026-04-05',
        )
        self.assertEqual(
            response.data['student_attendance'][0]['date'],
            '2026-04-05',
        )
        self.assertEqual(
            response.data['student_attendance'][0]['marked_by_name'],
            'Dr Timing',
        )

    def test_timing_analysis_month_rejects_invalid_format(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&year=2026&month=2026-13',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('month', response.data)

    def test_timing_analysis_month_must_belong_to_year(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&year=2026&month=2025-04',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('month', response.data)


class ProfessorYearlyAttendanceSummaryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Attendance Institute',
            admin_key='a' * 32,
            event_status='active',
        )
        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Summary',
            email='summary@example.com',
            phone_number='8888888888',
        )
        ProfessorExperience.objects.create(
            professor=self.professor,
            department='AI',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='SUMMARYPROF0001',
            employee_id='EMP-SUM',
        )
        self.published_professor = PublishedProfessor.objects.create(
            institute=self.institute,
            source_professor_id=self.professor.id,
            name=self.professor.name,
            email=self.professor.email,
            professor_personal_id='SUMMARYPROF0001',
            professor_data={
                'id': self.professor.id,
                'name': self.professor.name,
                'experience': {'department': 'AI'},
            },
        )
        self.url = reverse('data-analysis-professor-yearly-attendance')
        self.bulk_url = reverse('data-analysis-professor-yearly-attendance-bulk')
        self.performance_url = reverse('data-analysis-professor-attendance-performance')
        DefaultActivity.objects.create(
            institute=self.institute,
            session_month='Jan-Dec',
            session_year='2026-2027',
            academic_terms_type='semester',
            opening_time='08:00',
            closing_time='17:00',
            total_yearly_leaves=12,
        )

        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 10),
            status=True,
            attendance_time=time(7, 50),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 11),
            status=False,
            attendance_time=time(8, 30),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 3, 13),
            status=True,
            attendance_time=time(8, 10),
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name=self.professor.name,
            department='AI',
            email=self.professor.email,
            start_date=date(2025, 12, 31),
            end_date=date(2026, 1, 2),
            reason='New year break',
            leaves_status=ProfessorLeave.LeaveStatus.ACCEPTED,
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name=self.professor.name,
            department='AI',
            email=self.professor.email,
            start_date=date(2026, 3, 12),
            end_date=date(2026, 3, 13),
            reason='Conference',
            leaves_status=ProfessorLeave.LeaveStatus.ACCEPTED,
        )
        ProfessorLeave.objects.create(
            institute=self.institute,
            published_professor=self.published_professor,
            professor_name=self.professor.name,
            department='AI',
            email=self.professor.email,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 3),
            reason='Cancelled leave',
            leaves_status=ProfessorLeave.LeaveStatus.CANCELLED,
        )

    def test_professor_yearly_summary_requires_valid_professor(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&year=2026&professor=9999',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_professor_yearly_summary_counts_attendance_and_clipped_leaves(self):
        response = self.client.get(
            f'{self.url}?institute={self.institute.id}&year=2026&professor={self.professor.id}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['professor']['name'], 'Dr Summary')
        self.assertEqual(response.data['professor']['department'], 'AI')
        self.assertEqual(
            response.data['professor']['admin_employement']['employee_id'],
            'EMP-SUM',
        )

        january = response.data['months'][0]
        march = response.data['months'][2]
        april = response.data['months'][3]

        self.assertEqual(january['present'], 0)
        self.assertEqual(january['absent'], 2)
        self.assertEqual(january['acceptedLeaves'], 2)
        self.assertEqual(january['total'], 2)

        self.assertEqual(march['present'], 2)
        self.assertEqual(march['absent'], 2)
        self.assertEqual(march['acceptedLeaves'], 1)
        self.assertEqual(march['total'], 4)
        self.assertEqual(march['percentage'], 50)

        self.assertEqual(april['present'], 0)
        self.assertEqual(april['absent'], 0)
        self.assertEqual(april['acceptedLeaves'], 0)

        self.assertEqual(response.data['totals']['present'], 2)
        self.assertEqual(response.data['totals']['absent'], 4)
        self.assertEqual(response.data['totals']['acceptedLeaves'], 3)
        self.assertEqual(response.data['totals']['total'], 6)
        self.assertEqual(response.data['totals']['percentage'], 33)

    def test_professor_yearly_bulk_returns_summary_and_selected_year_records(self):
        other_professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Other Summary',
            email='other-summary@example.com',
            phone_number='5555555555',
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=other_professor,
            date=date(2026, 3, 10),
            status=True,
            attendance_time=time(7, 45),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2025, 12, 31),
            status=True,
            attendance_time=time(7, 40),
        )

        response = self.client.get(
            (
                f'{self.bulk_url}?institute={self.institute.id}'
                f'&year=2026&professor={self.professor.id}'
            ),
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['professor']['id'], self.professor.id)
        self.assertEqual(response.data['year'], 2026)
        self.assertEqual(response.data['opening_time'], '08:00:00')
        self.assertEqual(response.data['attendance_count'], 3)
        self.assertEqual(
            {record['date'] for record in response.data['attendance_records']},
            {'2026-03-10', '2026-03-11', '2026-03-13'},
        )
        self.assertEqual(
            {record['professor'] for record in response.data['attendance_records']},
            {self.professor.id},
        )
        self.assertEqual(
            response.data['attendance_records'][0]['attendance_time'],
            '07:50:00',
        )

        january = response.data['months'][0]
        march = response.data['months'][2]

        self.assertEqual(january['acceptedLeaves'], 2)
        self.assertEqual(march['present'], 2)
        self.assertEqual(march['absent'], 2)
        self.assertEqual(response.data['totals']['acceptedLeaves'], 3)
        self.assertEqual(response.data['totals']['total'], 6)

    def test_professor_yearly_summary_exposes_timing_performance_metrics(self):
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 1, 3),
            status=True,
            attendance_time=time(7, 55),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 1, 5),
            status=True,
            attendance_time=time(8, 10),
        )

        with patch('data_analysis.views.timezone.localdate', return_value=date(2026, 1, 6)):
            response = self.client.get(
                f'{self.url}?institute={self.institute.id}&year=2026&professor={self.professor.id}',
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['opening_time'], '08:00:00')
        self.assertEqual(response.data['totals']['on_time_days'], 1)
        self.assertEqual(response.data['totals']['late_days'], 1)
        self.assertEqual(response.data['totals']['missing_days'], 1)
        self.assertEqual(response.data['totals']['expected_working_days'], 3)
        self.assertEqual(response.data['totals']['on_time_percentage'], 33)
        self.assertEqual(response.data['totals']['late_percentage'], 33)

    def test_professor_attendance_performance_summary_returns_per_professor_metrics(self):
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 1, 3),
            status=True,
            attendance_time=time(7, 55),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 1, 5),
            status=True,
            attendance_time=time(8, 10),
        )

        with (
            patch('data_analysis.views.timezone.localdate', return_value=date(2026, 1, 6)),
            patch('data_analysis.attendance_analytics.timezone.localdate', return_value=date(2026, 1, 6)),
        ):
            response = self.client.get(
                (
                    f'{self.performance_url}?institute={self.institute.id}'
                    f'&year=2026&professor_ids={self.professor.id}'
                ),
                HTTP_X_ADMIN_KEY=self.institute.admin_key,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['professor_count'], 1)
        self.assertEqual(response.data['summary']['on_time_percentage'], 33)
        self.assertEqual(response.data['summary']['late_percentage'], 33)
        self.assertEqual(response.data['summary']['missing_days'], 1)

        professor_metrics = response.data['professors'][0]
        self.assertEqual(professor_metrics['professor']['name'], 'Dr Summary')
        self.assertEqual(professor_metrics['on_time_days'], 1)
        self.assertEqual(professor_metrics['late_days'], 1)
        self.assertEqual(professor_metrics['missing_days'], 1)
        self.assertEqual(professor_metrics['expected_working_days'], 3)


class AttendanceAnalyticsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institute = Institute.objects.create(
            name='Analytics Institute',
            admin_key='b' * 32,
            event_status='active',
        )
        self.current_timezone = timezone.get_current_timezone()
        DefaultActivity.objects.create(
            institute=self.institute,
            session_month='Jan-Dec',
            session_year='2026-2027',
            academic_terms_type='semester',
            opening_time='08:00',
            closing_time='17:00',
            total_yearly_leaves=12,
        )
        self.professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Analytics',
            email='analytics@example.com',
            phone_number='7777777777',
        )
        ProfessorExperience.objects.create(
            professor=self.professor,
            department='AI',
        )
        professorAdminEmployement.objects.create(
            professor=self.professor,
            personal_id='ANALYTICSPROF01',
            employee_id='EMP-ANL',
        )
        self.other_professor = Professor.objects.create(
            institute=self.institute,
            name='Dr Other',
            email='other@example.com',
            phone_number='6666666666',
        )
        ProfessorExperience.objects.create(
            professor=self.other_professor,
            department='CSE',
        )
        professorAdminEmployement.objects.create(
            professor=self.other_professor,
            personal_id='OTHERPROF0001',
            employee_id='EMP-OTH',
        )
        self.student = Student.objects.create(
            institute=self.institute,
            name='Analytics Student',
        )
        self.summary_url = reverse('data-analysis-attendance-analytics-summary')
        self.daily_url = reverse('data-analysis-attendance-analytics-professor-daily-times')
        self.submission_url = reverse('data-analysis-attendance-analytics-student-submission-times')
        self.weekly_url = reverse('data-analysis-attendance-analytics-weekly-trends')
        self.performance_url = reverse('data-analysis-professor-attendance-performance')

        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 1, 5),
            status=True,
            attendance_time=time(7, 50),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.professor,
            date=date(2026, 1, 6),
            status=True,
            attendance_time=time(8, 20),
        )
        ProfessorAttendance.objects.create(
            institute=self.institute,
            professor=self.other_professor,
            date=date(2026, 1, 5),
            status=True,
            attendance_time=time(8, 0),
        )
        self.create_submission(
            date(2026, 1, 5),
            'BA',
            'History',
            '1st Semester',
            time(7, 30),
        )
        self.create_submission(
            date(2026, 1, 5),
            'BSc',
            'Math',
            '1st Semester',
            time(7, 40),
        )
        self.create_submission(
            date(2026, 1, 6),
            'BA',
            'History',
            '2nd Semester',
            time(7, 55),
        )
        self.create_submission(
            date(2026, 1, 7),
            'BA',
            'History',
            '3rd Semester',
            time(7, 45),
        )

    def create_submission(self, submission_date, class_name, branch, term, submitted_time):
        submission = AttendanceSubmission.objects.create(
            institute=self.institute,
            date=submission_date,
            class_name=class_name,
            branch=branch,
            year_semester=term,
            marked_by=self.professor,
            submitted_at=timezone.make_aware(
                datetime.combine(submission_date, submitted_time),
                self.current_timezone,
            ),
        )
        Attendance.objects.create(
            student=self.student,
            submission=submission,
            status=True,
        )
        return submission

    def analytics_query(self, extra_params=''):
        base_query = (
            f'institute={self.institute.id}'
            f'&start_date=2026-01-05&end_date=2026-01-07'
            f'&professor_id={self.professor.id}'
        )
        return f'{base_query}{extra_params}'

    def test_summary_api_computes_status_and_delay_metrics(self):
        response = self.client.get(
            f'{self.summary_url}?{self.analytics_query()}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_professors'], 1)
        self.assertEqual(response.data['on_time_percentage'], 33)
        self.assertEqual(response.data['late_percentage'], 33)
        self.assertEqual(response.data['missing_attendance_days'], 1)
        self.assertEqual(response.data['average_delay_minutes'], 18.33)
        self.assertEqual(response.data['median_delay_minutes'], 20.0)
        self.assertEqual(response.data['deadline'], '08:00:00')

    def test_professor_daily_times_include_missing_working_days(self):
        response = self.client.get(
            f'{self.daily_url}?{self.analytics_query()}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        statuses_by_date = {
            row['date']: row
            for row in response.data['results']
        }
        self.assertEqual(statuses_by_date['2026-01-05']['status'], 'on_time')
        self.assertEqual(statuses_by_date['2026-01-05']['student_submission_count'], 2)
        self.assertEqual(statuses_by_date['2026-01-05']['average_delay_minutes'], 15.0)
        self.assertEqual(statuses_by_date['2026-01-06']['status'], 'late')
        self.assertEqual(statuses_by_date['2026-01-07']['status'], 'missing')
        self.assertIsNone(statuses_by_date['2026-01-07']['professor_check_time'])

    def test_student_submission_times_include_all_batches_and_null_delay(self):
        response = self.client.get(
            f'{self.submission_url}?{self.analytics_query()}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)
        delays = [row['delay_minutes'] for row in response.data['results']]
        self.assertEqual(delays[:3], [20.0, 10.0, 25.0])
        self.assertIsNone(delays[3])
        self.assertEqual(response.data['results'][3]['status'], 'missing')

    def test_performance_api_supports_date_range_metrics_and_department_filter(self):
        response = self.client.get(
            (
                f'{self.performance_url}?institute={self.institute.id}'
                '&start_date=2026-01-05&end_date=2026-01-07&department=AI'
            ),
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['professor_count'], 1)
        self.assertEqual(response.data['summary']['average_delay_minutes'], 18.33)
        professor_metrics = response.data['professors'][0]
        self.assertEqual(professor_metrics['professor_name'], 'Dr Analytics')
        self.assertEqual(professor_metrics['department'], 'AI')
        self.assertEqual(professor_metrics['average_delay_minutes'], 18.33)
        self.assertEqual(professor_metrics['median_delay_minutes'], 20.0)
        self.assertEqual(professor_metrics['missing_days'], 1)

    def test_weekly_trends_group_delay_and_status_counts(self):
        response = self.client.get(
            f'{self.weekly_url}?{self.analytics_query()}',
            HTTP_X_ADMIN_KEY=self.institute.admin_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        week = response.data['results'][0]
        self.assertEqual(week['average_delay_minutes'], 18.33)
        self.assertEqual(week['on_time_percentage'], 33)
        self.assertEqual(week['missing_count'], 1)
