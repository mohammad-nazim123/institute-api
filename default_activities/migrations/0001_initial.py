from datetime import time

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('iinstitutes_list', '0008_institute_academic_terms_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='DefaultActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_month', models.CharField(default='Jan-Dec', help_text='Academic/session month range, for example Jan-Dec.', max_length=7)),
                ('opening_time', models.TimeField(default=time(8, 0))),
                ('closing_time', models.TimeField(default=time(16, 0))),
                ('total_yearly_leaves', models.PositiveIntegerField(default=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('institute', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='default_activity', to='iinstitutes_list.institute')),
            ],
        ),
    ]
