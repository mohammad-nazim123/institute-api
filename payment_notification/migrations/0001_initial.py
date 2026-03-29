import payment_notification.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('iinstitutes_list', '0005_remove_schedules_and_unique_ids_artifacts'),
        ('professors', '0008_professor_search_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_month_key', models.CharField(max_length=7, validators=[payment_notification.models.payment_month_validator])),
                ('account_holder_name', models.CharField(max_length=1024)),
                ('bank_name', models.CharField(max_length=1024)),
                ('account_number', models.CharField(max_length=1024, validators=[payment_notification.models.account_number_validator])),
                ('ifsc_code', models.CharField(max_length=1024, validators=[payment_notification.models.ifsc_validator])),
                ('final_amount', models.CharField(max_length=1024)),
                ('payment_month', models.CharField(max_length=1024)),
                ('payment_date', models.CharField(max_length=1024)),
                ('approved_leaves', models.CharField(max_length=1024)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('institute', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='payment_notifications', to='iinstitutes_list.institute')),
                ('professor', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='payment_notifications', to='professors.professor')),
            ],
            options={
                'ordering': ['-payment_month_key', 'id'],
                'indexes': [
                    models.Index(fields=['institute', 'payment_month_key'], name='pay_note_inst_month_idx'),
                    models.Index(fields=['institute', 'professor'], name='pay_note_inst_prof_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('professor', 'payment_month_key'), name='uniq_payment_notification_prof_month'),
                ],
            },
        ),
    ]
