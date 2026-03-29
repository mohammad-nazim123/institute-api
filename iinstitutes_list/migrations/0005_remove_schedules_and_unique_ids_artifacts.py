from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iinstitutes_list', '0004_remove_institute_status_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DELETE FROM auth_permission
                WHERE content_type_id IN (
                    SELECT id FROM django_content_type
                    WHERE app_label IN ('schedules', 'unique_ids')
                );
                DELETE FROM django_content_type
                WHERE app_label IN ('schedules', 'unique_ids');
                DROP TABLE IF EXISTS schedules_examscheduledata;
                DROP TABLE IF EXISTS schedules_examscheduledate;
                DROP TABLE IF EXISTS schedules_weeklyscheduledata;
                DROP TABLE IF EXISTS schedules_weeklyscheduleday;
                DROP TABLE IF EXISTS schedules_scheduleacademicterm;
                DROP TABLE IF EXISTS schedules_schedulebranch;
                DROP TABLE IF EXISTS schedules_scheduleclass;
                DROP TABLE IF EXISTS schedules_examschedule;
                DROP TABLE IF EXISTS schedules_weeklyschedule;
                DROP TABLE IF EXISTS unique_ids_professoruniqueid;
                DROP TABLE IF EXISTS unique_ids_stuentuniqueid;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
