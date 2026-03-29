from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('professors', '0008_professor_search_indexes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='professor',
            name='age',
        ),
    ]
