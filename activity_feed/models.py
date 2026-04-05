from django.db import models
from django.utils import timezone


class ActivityEvent(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='activity_events',
    )
    actor_name = models.CharField(max_length=255, blank=True, default='')
    actor_role = models.CharField(max_length=100, blank=True, default='')
    actor_access_control = models.CharField(max_length=100, blank=True, default='')
    actor_source = models.CharField(max_length=40, blank=True, default='')
    action = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=80)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    entity_name = models.CharField(max_length=255, blank=True, default='')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    details = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-occurred_at', '-id']
        indexes = [
            models.Index(fields=['institute', 'occurred_at'], name='activity_feed_inst_time_idx'),
            models.Index(fields=['institute', 'entity_type'], name='activity_feed_inst_entity_idx'),
            models.Index(fields=['institute', 'actor_access_control'], name='activity_feed_inst_access_idx'),
        ]

    def __str__(self):
        return f'{self.institute_id} - {self.title}'
