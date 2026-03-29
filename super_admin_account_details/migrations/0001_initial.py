import super_admin_account_details.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SuperAdminAccountDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_holder_name', models.CharField(max_length=255)),
                ('bank_name', models.CharField(max_length=255)),
                ('account_number', models.CharField(max_length=20, validators=[super_admin_account_details.models.account_number_validator])),
                ('ifsc_code', models.CharField(max_length=11, validators=[super_admin_account_details.models.ifsc_validator])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
