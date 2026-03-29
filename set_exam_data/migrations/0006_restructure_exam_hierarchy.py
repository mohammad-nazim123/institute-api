from django.db import migrations, models
import django.db.models.deletion


def forward_fill_exam_hierarchy(apps, schema_editor):
    ExamClass = apps.get_model('set_exam_data', 'ExamClass')
    ExamBranch = apps.get_model('set_exam_data', 'ExamBranch')
    ExamAcedemicTerm = apps.get_model('set_exam_data', 'ExamAcedemicTerm')
    ExamData = apps.get_model('set_exam_data', 'ExamData')

    class_to_term = {}

    for exam_class in ExamClass.objects.all():
        exam_branch = ExamBranch.objects.create(
            exam_class=exam_class,
            branch=(exam_class.branch or '')[:20],
        )
        exam_term = ExamAcedemicTerm.objects.create(
            exam_branch=exam_branch,
            academic_term='',
        )
        class_to_term[exam_class.pk] = exam_term.pk

    for exam_data in ExamData.objects.all():
        exam_term_id = class_to_term.get(exam_data.exam_class_id)
        if exam_term_id is not None:
            exam_data.exam_academic_term_id = exam_term_id
            exam_data.save(update_fields=['exam_academic_term'])


def reverse_fill_exam_hierarchy(apps, schema_editor):
    ExamClass = apps.get_model('set_exam_data', 'ExamClass')
    ExamData = apps.get_model('set_exam_data', 'ExamData')

    for exam_class in ExamClass.objects.all():
        first_branch = exam_class.exam_branch.order_by('id').first()
        exam_class.branch = first_branch.branch if first_branch else ''
        exam_class.save(update_fields=['branch'])

    for exam_data in ExamData.objects.select_related('exam_academic_term__exam_branch__exam_class'):
        exam_data.exam_class = exam_data.exam_academic_term.exam_branch.exam_class
        exam_data.save(update_fields=['exam_class'])


class Migration(migrations.Migration):

    dependencies = [
        ('set_exam_data', '0005_examclass_branch'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamBranch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('branch', models.CharField(default='', max_length=20)),
                ('exam_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_branch', to='set_exam_data.examclass')),
            ],
        ),
        migrations.CreateModel(
            name='ExamAcedemicTerm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('academic_term', models.CharField(default='', max_length=15)),
                ('exam_branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_academic_terms', to='set_exam_data.exambranch')),
            ],
        ),
        migrations.AddField(
            model_name='examdata',
            name='exam_academic_term',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='exam_data', to='set_exam_data.examacedemicterm'),
        ),
        migrations.RunPython(forward_fill_exam_hierarchy, reverse_fill_exam_hierarchy),
        migrations.RemoveField(
            model_name='examdata',
            name='exam_class',
        ),
        migrations.RemoveField(
            model_name='examclass',
            name='branch',
        ),
        migrations.AlterField(
            model_name='examdata',
            name='exam_academic_term',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_data', to='set_exam_data.examacedemicterm'),
        ),
    ]
