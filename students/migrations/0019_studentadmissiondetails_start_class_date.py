from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('students', '0018_student_student_institute_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentadmissiondetails',
            name='start_class_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
