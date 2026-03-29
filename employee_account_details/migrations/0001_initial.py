import employee_account_details.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('iinstitutes_list', '0005_remove_schedules_and_unique_ids_artifacts'),
        ('professors', '0008_professor_search_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeAccountDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_holder_name', models.CharField(max_length=255)),
                ('bank_name', models.CharField(max_length=255)),
                ('account_number', models.CharField(max_length=20, validators=[employee_account_details.models.account_number_validator])),
                ('ifsc_code', models.CharField(max_length=11, validators=[employee_account_details.models.ifsc_validator])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('institute', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='employee_account_details', to='iinstitutes_list.institute')),
                ('professor', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='account_detail', to='professors.professor')),
            ],
            options={
                'ordering': ['id'],
                'indexes': [models.Index(fields=['institute', 'professor'], name='emp_acc_inst_prof_idx')],
            },
        ),
    ]
