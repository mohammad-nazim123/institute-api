from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('super_admin_account_details', '0003_encrypt_sensitive_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='superadminaccountdetail',
            name='card_design',
            field=models.CharField(
                choices=[('golden', 'Golden'), ('platinum', 'Platinum'), ('diamond', 'Diamond')],
                default='golden',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='superadminaccountdetail',
            name='is_default',
            field=models.BooleanField(default=False),
        ),
    ]
