from datetime import time

from django.db import models
from django.utils import timezone


def get_default_session_year():
    session_start_year = timezone.localdate().year
    return f'{session_start_year}-{session_start_year + 1}'


class DefaultActivity(models.Model):
    institute = models.OneToOneField(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='default_activity',
    )
    session_month = models.CharField(
        max_length=7,
        default='Jan-Dec',
        help_text='Academic/session month range, for example Jan-Dec.',
    )
    session_year = models.CharField(
        max_length=9,
        default=get_default_session_year,
        help_text='Academic session year range, for example 2026-2027.',
    )
    opening_time = models.TimeField(default=time(8, 0))
    closing_time = models.TimeField(default=time(16, 0))
    total_yearly_leaves = models.PositiveIntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.institute_id} - {self.session_year} - {self.session_month}'
