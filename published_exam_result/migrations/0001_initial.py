import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('iinstitutes_list', '0007_rename_name_add_super_admin_name'),
        ('published_student', '0002_remove_publishedstudent_pub_student_key_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublishedExamResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_student_id', models.PositiveBigIntegerField()),
                ('name', models.CharField(db_index=True, default='', max_length=100)),
                ('student_personal_id', models.CharField(db_index=True, default='', max_length=50)),
                ('exam_results', models.JSONField(default=list)),
                ('published_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('institute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='published_exam_results', to='iinstitutes_list.institute')),
                ('published_student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='published_exam_result', to='published_student.publishedstudent')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['institute', 'source_student_id'], name='pub_exam_res_lookup_idx'),
                    models.Index(fields=['institute', 'name'], name='pub_exam_res_name_idx'),
                    models.Index(fields=['institute', 'student_personal_id'], name='pub_exam_res_pid_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('institute', 'source_student_id'), name='uniq_pub_exam_result_inst_source'),
                ],
            },
        ),
    ]
