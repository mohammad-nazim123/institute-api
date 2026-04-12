import default_activities.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('default_activities', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='defaultactivity',
            name='session_year',
            field=models.CharField(
                default=default_activities.models.get_default_session_year,
                help_text='Academic session year range, for example 2026-2027.',
                max_length=9,
            ),
        ),
    ]
