from django.db import migrations, models
from django.db.models import F


def copy_existing_attendance_times(apps, schema_editor):
    ProfessorAttendance = apps.get_model('professor_attendance', 'ProfessorAttendance')

    ProfessorAttendance.objects.filter(
        present_time__isnull=False,
    ).update(attendance_time=F('present_time'))

    ProfessorAttendance.objects.filter(
        attendance_time__isnull=True,
        absent_time__isnull=False,
    ).update(attendance_time=F('absent_time'))


class Migration(migrations.Migration):

    dependencies = [
        ('professor_attendance', '0002_professorattendance_status_times'),
    ]

    operations = [
        migrations.AddField(
            model_name='professorattendance',
            name='attendance_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.RunPython(copy_existing_attendance_times, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='professorattendance',
            name='absent_time',
        ),
        migrations.RemoveField(
            model_name='professorattendance',
            name='present_time',
        ),
    ]
