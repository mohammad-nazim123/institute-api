from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('professor_attendance', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='professorattendance',
            name='absent_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='professorattendance',
            name='present_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
