from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subordinate_access', '0002_subordinateaccessverificationrequest'),
    ]

    operations = [
        migrations.RenameField(
            model_name='subordinateaccess',
            old_name='is_varified',
            new_name='is_active',
        ),
        migrations.AlterField(
            model_name='subordinateaccess',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
