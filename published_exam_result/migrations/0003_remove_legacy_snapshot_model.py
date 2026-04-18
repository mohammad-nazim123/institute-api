from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('published_exam_result', '0002_relational_published_exam_results'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PublishedExamResult',
        ),
    ]
