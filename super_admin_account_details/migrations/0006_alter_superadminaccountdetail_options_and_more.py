from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('super_admin_account_details', '0005_merge_0004_name_and_card_design'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='superadminaccountdetail',
            options={'ordering': ['-is_default', 'id']},
        ),
        migrations.AlterField(
            model_name='superadminaccountdetail',
            name='name',
            field=models.CharField(blank=True, default='', editable=False, max_length=255),
        ),
    ]
