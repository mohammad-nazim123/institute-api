from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def move_common_attendance_fields_to_submissions(apps, schema_editor):
    Attendance = apps.get_model('attendance', 'Attendance')
    AttendanceSubmission = apps.get_model('attendance', 'AttendanceSubmission')

    for attendance in Attendance.objects.select_related('student', 'marked_by').all().iterator():
        institute_id = getattr(attendance.student, 'institute_id', None)
        if not institute_id:
            continue

        submission, created = AttendanceSubmission.objects.get_or_create(
            institute_id=institute_id,
            date=attendance.date,
            class_name=attendance.class_name or '',
            branch=attendance.branch or '',
            year_semester=attendance.year_semester or '',
            defaults={
                'marked_by_id': attendance.marked_by_id,
                'submitted_at': attendance.submitted_at,
            },
        )

        if not created:
            update_fields = []
            if attendance.submitted_at and attendance.submitted_at > submission.submitted_at:
                submission.submitted_at = attendance.submitted_at
                update_fields.append('submitted_at')
            if attendance.marked_by_id and submission.marked_by_id != attendance.marked_by_id:
                submission.marked_by_id = attendance.marked_by_id
                update_fields.append('marked_by')
            if update_fields:
                submission.save(update_fields=update_fields)

        attendance.submission_id = submission.id
        attendance.save(update_fields=['submission'])


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_attendance_submitted_at'),
        ('iinstitutes_list', '0009_remove_institute_academic_terms_type'),
        ('professors', '0009_remove_professor_age'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('class_name', models.CharField(default='', max_length=50)),
                ('branch', models.CharField(default='', max_length=30)),
                ('year_semester', models.CharField(default='', max_length=20)),
                ('submitted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('institute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_attendance_submissions', to='iinstitutes_list.institute')),
                ('marked_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='professors.professor')),
            ],
        ),
        migrations.AddField(
            model_name='attendance',
            name='submission',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='attendance.attendancesubmission'),
        ),
        migrations.RunPython(
            move_common_attendance_fields_to_submissions,
            migrations.RunPython.noop,
        ),
        migrations.AlterUniqueTogether(
            name='attendance',
            unique_together=set(),
        ),
        migrations.RemoveIndex(
            model_name='attendance',
            name='att_student_date_idx',
        ),
        migrations.RemoveIndex(
            model_name='attendance',
            name='att_class_branch_date_idx',
        ),
        migrations.RemoveField(
            model_name='attendance',
            name='branch',
        ),
        migrations.RemoveField(
            model_name='attendance',
            name='class_name',
        ),
        migrations.RemoveField(
            model_name='attendance',
            name='date',
        ),
        migrations.RemoveField(
            model_name='attendance',
            name='marked_by',
        ),
        migrations.RemoveField(
            model_name='attendance',
            name='submitted_at',
        ),
        migrations.RemoveField(
            model_name='attendance',
            name='year_semester',
        ),
        migrations.AlterField(
            model_name='attendance',
            name='submission',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='attendance.attendancesubmission'),
        ),
        migrations.AddConstraint(
            model_name='attendancesubmission',
            constraint=models.UniqueConstraint(fields=('institute', 'date', 'class_name', 'branch', 'year_semester'), name='uniq_student_attendance_submission'),
        ),
        migrations.AddIndex(
            model_name='attendancesubmission',
            index=models.Index(fields=['institute', 'date'], name='att_sub_inst_date_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancesubmission',
            index=models.Index(fields=['class_name', 'branch', 'date'], name='att_sub_class_branch_date_idx'),
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(fields=('student', 'submission'), name='uniq_student_attendance_record'),
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['student', 'submission'], name='att_student_submission_idx'),
        ),
    ]
