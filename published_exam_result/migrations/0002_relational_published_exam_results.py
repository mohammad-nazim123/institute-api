import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def backfill_relational_published_exam_results(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    PublishedStudent = apps.get_model('published_student', 'PublishedStudent')
    PublishedExamData = apps.get_model('published_exam_result', 'PublishedExamData')
    PublishedObtainedMarks = apps.get_model('published_exam_result', 'PublishedObtainedMarks')
    ObtainedMarks = apps.get_model('set_exam_data', 'ObtainedMarks')
    now = django.utils.timezone.now()

    published_student_map = {
        (student.institute_id, student.source_student_id): student.id
        for student in PublishedStudent.objects.using(db_alias).all()
    }
    if not published_student_map:
        return

    marks = list(
        ObtainedMarks.objects.using(db_alias)
        .select_related('exam_data')
        .order_by('id')
    )
    if not marks:
        return

    published_exam_data_by_source = {}
    for mark in marks:
        exam_data = getattr(mark, 'exam_data', None)
        if exam_data is None:
            continue
        if (exam_data.institute_id, mark.student_id) not in published_student_map:
            continue
        if exam_data.id in published_exam_data_by_source:
            continue

        published_exam_data_by_source[exam_data.id] = PublishedExamData(
            institute_id=exam_data.institute_id,
            source_exam_data_id=exam_data.id,
            class_name=exam_data.class_name or '',
            branch=exam_data.branch or '',
            academic_term=exam_data.academic_term or '',
            subject=exam_data.subject or '',
            exam_type=exam_data.exam_type or '',
            date=exam_data.date,
            duration=exam_data.duration or 0,
            total_marks=exam_data.total_marks or 0,
            published_at=now,
            updated_at=now,
        )

    if published_exam_data_by_source:
        PublishedExamData.objects.using(db_alias).bulk_create(
            list(published_exam_data_by_source.values()),
            ignore_conflicts=True,
            batch_size=1000,
        )

    published_exam_data_ids = {
        item.source_exam_data_id: item.id
        for item in PublishedExamData.objects.using(db_alias)
        .filter(source_exam_data_id__in=published_exam_data_by_source.keys())
    }

    published_marks = []
    for mark in marks:
        exam_data = getattr(mark, 'exam_data', None)
        if exam_data is None:
            continue

        published_student_id = published_student_map.get((exam_data.institute_id, mark.student_id))
        published_exam_data_id = published_exam_data_ids.get(mark.exam_data_id)
        if not published_student_id or not published_exam_data_id:
            continue

        published_marks.append(
            PublishedObtainedMarks(
                published_exam_data_id=published_exam_data_id,
                published_student_id=published_student_id,
                source_obtained_marks_id=mark.id,
                obtained_marks=mark.obtained_marks,
                published_at=now,
                updated_at=now,
            )
        )

    if published_marks:
        PublishedObtainedMarks.objects.using(db_alias).bulk_create(
            published_marks,
            ignore_conflicts=True,
            batch_size=1000,
        )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('published_exam_result', '0001_initial'),
        ('set_exam_data', '0009_flat_exam_data_redesign'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublishedExamData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_exam_data_id', models.PositiveBigIntegerField(unique=True)),
                ('class_name', models.CharField(default='', max_length=40)),
                ('branch', models.CharField(default='', max_length=100)),
                ('academic_term', models.CharField(default='', max_length=15)),
                ('subject', models.CharField(default='', max_length=40)),
                ('exam_type', models.CharField(default='', max_length=10)),
                ('date', models.DateField(blank=True, null=True)),
                ('duration', models.IntegerField(default=0)),
                ('total_marks', models.IntegerField(default=0)),
                ('published_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('institute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='published_exam_data', to='iinstitutes_list.institute')),
            ],
            options={
                'db_table': 'published_exam_data',
                'indexes': [
                    models.Index(fields=['institute', 'class_name', 'branch', 'academic_term', 'exam_type'], name='pub_exam_data_scope_idx'),
                    models.Index(fields=['institute', 'subject'], name='pub_exam_data_subject_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='PublishedObtainedMarks',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_obtained_marks_id', models.PositiveBigIntegerField(unique=True)),
                ('obtained_marks', models.IntegerField(default=0)),
                ('published_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('published_exam_data', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='published_obtained_marks', to='published_exam_result.publishedexamdata')),
                ('published_student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='published_exam_results', to='published_student.publishedstudent')),
            ],
            options={
                'db_table': 'published_obtained_marks',
                'indexes': [
                    models.Index(fields=['published_student'], name='pub_obt_marks_student_idx'),
                    models.Index(fields=['published_exam_data'], name='pub_obt_marks_exam_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('published_exam_data', 'published_student'), name='uniq_pub_exam_data_student'),
                ],
            },
        ),
        migrations.RunPython(backfill_relational_published_exam_results, noop_reverse),
    ]
