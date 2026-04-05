from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('super_admin_account_details', '0003_encrypt_sensitive_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='superadminaccountdetail',
            name='name',
            field=models.CharField(default='', max_length=255),
        ),
    ]
