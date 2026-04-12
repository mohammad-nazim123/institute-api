from datetime import time

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('professor_leaves', '0007_institutetotalleave'),
    ]

    operations = [
        migrations.AddField(
            model_name='institutetotalleave',
            name='closing_time',
            field=models.TimeField(default=time(18, 0)),
        ),
        migrations.AddField(
            model_name='institutetotalleave',
            name='opening_time',
            field=models.TimeField(default=time(8, 0)),
        ),
        migrations.AddField(
            model_name='institutetotalleave',
            name='session_end_month',
            field=models.PositiveSmallIntegerField(default=3),
        ),
        migrations.AddField(
            model_name='institutetotalleave',
            name='session_start_month',
            field=models.PositiveSmallIntegerField(default=4),
        ),
    ]
