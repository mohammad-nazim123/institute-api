from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('iinstitutes_list', '0007_rename_name_add_super_admin_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actor_name', models.CharField(blank=True, default='', max_length=255)),
                ('actor_role', models.CharField(blank=True, default='', max_length=100)),
                ('actor_access_control', models.CharField(blank=True, default='', max_length=100)),
                ('actor_source', models.CharField(blank=True, default='', max_length=40)),
                ('action', models.CharField(max_length=50)),
                ('entity_type', models.CharField(max_length=80)),
                ('entity_id', models.PositiveIntegerField(blank=True, null=True)),
                ('entity_name', models.CharField(blank=True, default='', max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('details', models.JSONField(blank=True, default=dict)),
                ('occurred_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('institute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_events', to='iinstitutes_list.institute')),
            ],
            options={
                'ordering': ['-occurred_at', '-id'],
                'indexes': [
                    models.Index(fields=['institute', 'occurred_at'], name='activity_feed_inst_time_idx'),
                    models.Index(fields=['institute', 'entity_type'], name='activity_feed_inst_entity_idx'),
                    models.Index(fields=['institute', 'actor_access_control'], name='activity_feed_inst_access_idx'),
                ],
            },
        ),
    ]
