from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iinstitutes_list', '0006_institute_institute_name_idx'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='institute',
            name='institute_name_idx',
        ),
        migrations.RenameField(
            model_name='institute',
            old_name='name',
            new_name='institute_name',
        ),
        migrations.AlterField(
            model_name='institute',
            name='institute_name',
            field=models.CharField(max_length=255, verbose_name='Institute name'),
        ),
        migrations.AddField(
            model_name='institute',
            name='super_admin_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddIndex(
            model_name='institute',
            index=models.Index(fields=['institute_name'], name='institute_name_idx'),
        ),
    ]
