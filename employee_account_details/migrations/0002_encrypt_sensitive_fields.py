import employee_account_details.models
from django.db import migrations, models

from institute_api.encryption import encrypt_value, is_encrypted_value


ENCRYPTED_FIELDS = (
    'account_holder_name',
    'bank_name',
    'account_number',
    'ifsc_code',
)


def encrypt_existing_employee_account_details(apps, schema_editor):
    EmployeeAccountDetail = apps.get_model('employee_account_details', 'EmployeeAccountDetail')

    for record in EmployeeAccountDetail.objects.all().iterator():
        updates = {}
        for field_name in ENCRYPTED_FIELDS:
            value = getattr(record, field_name)
            if value and not is_encrypted_value(value):
                updates[field_name] = encrypt_value(value)
        if updates:
            EmployeeAccountDetail.objects.filter(pk=record.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('employee_account_details', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employeeaccountdetail',
            name='account_holder_name',
            field=models.CharField(max_length=1024),
        ),
        migrations.AlterField(
            model_name='employeeaccountdetail',
            name='bank_name',
            field=models.CharField(max_length=1024),
        ),
        migrations.AlterField(
            model_name='employeeaccountdetail',
            name='account_number',
            field=models.CharField(
                max_length=1024,
                validators=[employee_account_details.models.account_number_validator],
            ),
        ),
        migrations.AlterField(
            model_name='employeeaccountdetail',
            name='ifsc_code',
            field=models.CharField(
                max_length=1024,
                validators=[employee_account_details.models.ifsc_validator],
            ),
        ),
        migrations.RunPython(
            encrypt_existing_employee_account_details,
            migrations.RunPython.noop,
        ),
    ]
