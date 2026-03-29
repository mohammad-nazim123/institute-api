from django.db import migrations, models


def copy_course_details_into_assignments(apps, schema_editor):
    StudentCourseAssignment = apps.get_model('students', 'StudentCourseAssignment')
    StudentCourseDetails = apps.get_model('students', 'StudentCourseDetails')

    details_by_student_id = {
        details.student_id: details
        for details in StudentCourseDetails.objects.all().only('student_id', 'course_name', 'branch')
    }

    assignment_student_ids = set()

    for assignment in StudentCourseAssignment.objects.all():
        assignment_student_ids.add(assignment.student_id)
        details = details_by_student_id.get(assignment.student_id)
        updates = []

        if details and details.course_name and not assignment.class_name:
            assignment.class_name = details.course_name
            updates.append('class_name')

        if details and details.branch:
            assignment.branch = details.branch
            updates.append('branch')

        if updates:
            assignment.save(update_fields=updates)

    for student_id, details in details_by_student_id.items():
        if student_id in assignment_student_ids:
            continue

        StudentCourseAssignment.objects.create(
            student_id=student_id,
            class_name=details.course_name,
            branch=details.branch,
            academic_term='',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0015_subjectsassigned'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='student',
            name='age',
        ),
        migrations.AddField(
            model_name='studentcontactdetails',
            name='guardian_name',
            field=models.CharField(default='', max_length=30),
        ),
        migrations.RenameField(
            model_name='studentcourseassignment',
            old_name='course_name',
            new_name='class_name',
        ),
        migrations.RenameField(
            model_name='studentcourseassignment',
            old_name='year',
            new_name='academic_term',
        ),
        migrations.AddField(
            model_name='studentcourseassignment',
            name='branch',
            field=models.CharField(default='', max_length=100),
        ),
        migrations.RunPython(copy_course_details_into_assignments, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='studentcourseassignment',
            name='batch',
        ),
        migrations.DeleteModel(
            name='StudentCourseDetails',
        ),
    ]
