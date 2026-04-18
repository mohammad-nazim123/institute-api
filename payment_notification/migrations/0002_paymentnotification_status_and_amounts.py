from django.db import migrations, models
from django.db.models import F

from institute_api.encryption import encrypt_value


def backfill_payment_notification_amounts(apps, schema_editor):
    PaymentNotification = apps.get_model('payment_notification', 'PaymentNotification')

    PaymentNotification.objects.all().update(
        status='pending',
        gross_amount=F('final_amount'),
        deducted_amount=encrypt_value('0.00'),
    )


def reverse_backfill_payment_notification_amounts(apps, schema_editor):
    PaymentNotification = apps.get_model('payment_notification', 'PaymentNotification')

    PaymentNotification.objects.all().update(
        status='pending',
        gross_amount='0',
        deducted_amount='0',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('payment_notification', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentnotification',
            name='deducted_amount',
            field=models.CharField(default='0', max_length=1024),
        ),
        migrations.AddField(
            model_name='paymentnotification',
            name='gross_amount',
            field=models.CharField(default='0', max_length=1024),
        ),
        migrations.AddField(
            model_name='paymentnotification',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name='paymentnotification',
            index=models.Index(
                fields=['institute', 'status'],
                name='pay_note_inst_status_idx',
            ),
        ),
        migrations.RunPython(
            backfill_payment_notification_amounts,
            reverse_backfill_payment_notification_amounts,
        ),
    ]
