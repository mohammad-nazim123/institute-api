from django.core.management.base import BaseCommand
from django.utils import timezone
from iinstitutes_list.models import Institute


class Command(BaseCommand):
    help = 'Auto-stop institutes whose event timer has expired.'

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Institute.objects.filter(
            event_status='active',
            event_timer_end__isnull=False,
            event_timer_end__lte=now,
        )
        count = expired.update(event_status='stopped')
        self.stdout.write(
            self.style.SUCCESS(f'{count} institute(s) auto-stopped due to expired timer.')
        )
