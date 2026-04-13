from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('default_activities', '0003_academicterm'),
    ]

    operations = [
        migrations.AddField(
            model_name='defaultactivity',
            name='academic_terms_type',
            field=models.CharField(
                choices=[('semester', 'Semester Wise'), ('year', 'Year Wise')],
                default='semester',
                help_text='Choose whether this institute uses semester-wise or year-wise academic terms.',
                max_length=20,
            ),
        ),
    ]
