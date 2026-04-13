import django.db.models.deletion
from django.db import migrations, models


def ordinal_label(number):
    if 10 <= (number % 100) <= 20:
        suffix = 'th'
    else:
        suffix = {
            1: 'st',
            2: 'nd',
            3: 'rd',
        }.get(number % 10, 'th')
    return f'{number}{suffix}'


def build_terms(academic_terms_type):
    normalized_type = str(academic_terms_type or '').strip().lower()
    suffix = 'Year' if normalized_type == 'year' else 'Semester'
    total = 4 if normalized_type == 'year' else 8
    return [
        f'{ordinal_label(index)} {suffix}'
        for index in range(1, total + 1)
    ]


def populate_academic_terms(apps, schema_editor):
    AcademicTerm = apps.get_model('default_activities', 'AcademicTerm')
    Institute = apps.get_model('iinstitutes_list', 'Institute')

    academic_terms_to_create = []
    for institute in Institute.objects.all().only('id', 'academic_terms_type'):
        for sort_order, term_name in enumerate(
            build_terms(getattr(institute, 'academic_terms_type', 'semester')),
            start=1,
        ):
            academic_terms_to_create.append(
                AcademicTerm(
                    institute_id=institute.id,
                    name=term_name,
                    sort_order=sort_order,
                )
            )

    if academic_terms_to_create:
        AcademicTerm.objects.bulk_create(academic_terms_to_create)


class Migration(migrations.Migration):

    dependencies = [
        ('default_activities', '0002_defaultactivity_session_year'),
        ('iinstitutes_list', '0008_institute_academic_terms_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='AcademicTerm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('sort_order', models.PositiveIntegerField(default=1, help_text='Lower values appear first in academic term lists.')),
                ('institute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='configured_academic_terms', to='iinstitutes_list.institute')),
            ],
            options={
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='academicterm',
            index=models.Index(fields=['institute', 'sort_order'], name='acterm_inst_sort_idx'),
        ),
        migrations.AddConstraint(
            model_name='academicterm',
            constraint=models.UniqueConstraint(fields=('institute', 'name'), name='default_activity_term_inst_name_uniq'),
        ),
        migrations.RunPython(populate_academic_terms, migrations.RunPython.noop),
    ]
