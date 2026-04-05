from django.db import migrations


LEGACY_TABLES = (
    'schedules_examscheduledata',
    'schedules_examscheduledate',
    'schedules_weeklyscheduledata',
    'schedules_weeklyscheduleday',
    'schedules_scheduleacademicterm',
    'schedules_schedulebranch',
    'schedules_scheduleclass',
    'schedules_examschedule',
    'schedules_weeklyschedule',
    'unique_ids_professoruniqueid',
    'unique_ids_stuentuniqueid',
)


def remove_legacy_artifacts(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())

    with schema_editor.connection.cursor() as cursor:
        if 'auth_permission' in existing_tables and 'django_content_type' in existing_tables:
            cursor.execute(
                """
                DELETE FROM auth_permission
                WHERE content_type_id IN (
                    SELECT id FROM django_content_type
                    WHERE app_label IN ('schedules', 'unique_ids')
                )
                """
            )

        if 'django_content_type' in existing_tables:
            cursor.execute(
                """
                DELETE FROM django_content_type
                WHERE app_label IN ('schedules', 'unique_ids')
                """
            )

        for table_name in LEGACY_TABLES:
            cursor.execute(f'DROP TABLE IF EXISTS {table_name}')


class Migration(migrations.Migration):

    dependencies = [
        ('iinstitutes_list', '0004_remove_institute_status_and_more'),
    ]

    operations = [
        migrations.RunPython(remove_legacy_artifacts, reverse_code=migrations.RunPython.noop),
    ]
