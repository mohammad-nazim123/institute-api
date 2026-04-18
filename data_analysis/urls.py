from django.urls import path

from .views import (
    AttendanceAnalyticsProfessorDailyTimesView,
    AttendanceAnalyticsStudentSubmissionTimesView,
    AttendanceAnalyticsSummaryView,
    AttendanceAnalyticsWeeklyTrendsView,
    ProfessorAttendancePerformanceSummaryView,
    ProfessorYearlyAttendanceBulkView,
    ProfessorYearlyAttendanceSummaryView,
    TimingAnalysisBulkView,
)


urlpatterns = [
    path(
        'timing-analysis/',
        TimingAnalysisBulkView.as_view(),
        name='data-analysis-timing-analysis',
    ),
    path(
        'professor-yearly-attendance/',
        ProfessorYearlyAttendanceSummaryView.as_view(),
        name='data-analysis-professor-yearly-attendance',
    ),
    path(
        'professor-yearly-attendance-bulk/',
        ProfessorYearlyAttendanceBulkView.as_view(),
        name='data-analysis-professor-yearly-attendance-bulk',
    ),
    path(
        'professor-attendance-performance/',
        ProfessorAttendancePerformanceSummaryView.as_view(),
        name='data-analysis-professor-attendance-performance',
    ),
    path(
        'attendance-analytics/summary/',
        AttendanceAnalyticsSummaryView.as_view(),
        name='data-analysis-attendance-analytics-summary',
    ),
    path(
        'attendance-analytics/professor-daily-times/',
        AttendanceAnalyticsProfessorDailyTimesView.as_view(),
        name='data-analysis-attendance-analytics-professor-daily-times',
    ),
    path(
        'attendance-analytics/student-submission-times/',
        AttendanceAnalyticsStudentSubmissionTimesView.as_view(),
        name='data-analysis-attendance-analytics-student-submission-times',
    ),
    path(
        'attendance-analytics/weekly-trends/',
        AttendanceAnalyticsWeeklyTrendsView.as_view(),
        name='data-analysis-attendance-analytics-weekly-trends',
    ),
]
