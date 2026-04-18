from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_add_attendance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='submitted_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
