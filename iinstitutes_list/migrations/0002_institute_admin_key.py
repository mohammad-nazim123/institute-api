import secrets
from django.db import migrations, models


def backfill_admin_keys(apps, schema_editor):
    """Assign a unique 32-char hex key to every existing Institute row."""
    Institute = apps.get_model('iinstitutes_list', 'Institute')
    existing_keys = set(
        Institute.objects.exclude(admin_key='').values_list('admin_key', flat=True)
    )
    for institute in Institute.objects.filter(admin_key=''):
        while True:
            key = secrets.token_hex(16)
            if key not in existing_keys:
                existing_keys.add(key)
                break
        institute.admin_key = key
        institute.save(update_fields=['admin_key'])


class Migration(migrations.Migration):

    dependencies = [
        ('iinstitutes_list', '0001_initial'),
    ]

    operations = [
        # Step 1: Add the column as nullable with no unique constraint yet
        migrations.AddField(
            model_name='institute',
            name='admin_key',
            field=models.CharField(
                default='',
                editable=False,
                help_text='Auto-generated 32-digit hex key for admin access',
                max_length=32,
            ),
        ),
        # Step 2: Backfill each existing row with a unique key
        migrations.RunPython(backfill_admin_keys, migrations.RunPython.noop),
        # Step 3: Now add the unique constraint and set default for new rows
        migrations.AlterField(
            model_name='institute',
            name='admin_key',
            field=models.CharField(
                default='',
                editable=False,
                help_text='Auto-generated 32-digit hex key for admin access',
                max_length=32,
                unique=True,
            ),
        ),
    ]
