from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0005_normalize_student_attendance_submissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancesubmission',
            name='attendance_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
