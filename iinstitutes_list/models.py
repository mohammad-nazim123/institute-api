import secrets
from django.db import models


def generate_unique_key():
    """Generate a unique 32-character hex key."""
    return secrets.token_hex(16)  # 32 hex characters


EVENT_STATUS_CHOICES = [
    ('active', 'Active'),
    ('paused', 'Paused'),
    ('stopped', 'Stopped'),
]


class Institute(models.Model):
    name = models.CharField(max_length=255)
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

    @property
    def is_event_active(self):
        """Returns True only when event_status is active."""
        return self.event_status == 'active'

    def __str__(self):
        return self.name
