import secrets
from django.db import models
from .academic_terms import ACADEMIC_TERMS_TYPE_CHOICES, get_academic_terms_for_institute


def generate_unique_key():
    """Generate a unique 32-character hex key."""
    return secrets.token_hex(16)  # 32 hex characters


EVENT_STATUS_CHOICES = [
    ('active', 'Active'),
    ('paused', 'Paused'),
    ('stopped', 'Stopped'),
]


class Institute(models.Model):
    institute_name = models.CharField(max_length=255, verbose_name='Institute name')
    super_admin_name = models.CharField(max_length=255, blank=True, default='')
    academic_terms_type = models.CharField(
        max_length=20,
        choices=ACADEMIC_TERMS_TYPE_CHOICES,
        default='semester',
        help_text='Choose whether this institute uses semester-wise or year-wise academic terms.',
    )
    admin_key = models.CharField(
        max_length=32,
        unique=True,
        default='',
        editable=False,
        help_text='Auto-generated 32-digit hex key for admin access'
    )
    event_status = models.CharField(
        max_length=10,
        choices=EVENT_STATUS_CHOICES,
        default='active',
        help_text='Controls whether this institute\'s events are accessible'
    )
    event_timer_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When set, events auto-stop after this date/time'
    )

    class Meta:
        indexes = [
            models.Index(fields=['institute_name'], name='institute_name_idx'),
        ]

    @property
    def is_event_active(self):
        """Returns True only when event_status is active."""
        return self.event_status == 'active'

    @property
    def name(self):
        return self.institute_name

    @name.setter
    def name(self, value):
        self.institute_name = value

    @property
    def academic_terms(self):
        return get_academic_terms_for_institute(self)

    def __str__(self):
        return self.institute_name
