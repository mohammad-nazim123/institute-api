from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iinstitutes_list', '0005_remove_schedules_and_unique_ids_artifacts'),
        ('super_admin_account_details', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='superadminaccountdetail',
            name='institute',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='super_admin_account_details',
                to='iinstitutes_list.institute',
            ),
        ),
    ]
