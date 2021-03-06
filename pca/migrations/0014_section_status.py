# Generated by Django 2.1.7 on 2019-04-05 20:41

from django.db import migrations, models


def forwards(apps, schema_editor):
    Section = apps.get_model('pca', 'Section')
    for sec in Section.objects.all():
        if sec.is_open:
            sec.status = 'O'
        else:
            sec.status = 'C'

        sec.save()


def backwards(apps, schema_editor):
    Section = apps.get_model('pca', 'Section')
    for sec in Section.objects.all():
        sec.is_open = sec.status == 'O'
        sec.save()


class Migration(migrations.Migration):

    dependencies = [
        ('pca', '0013_auto_20190322_2043'),
    ]

    operations = [
        migrations.AddField(
            model_name='section',
            name='status',
            field=models.CharField(choices=[('O', 'Open'), ('C', 'Closed'), ('X', 'Cancelled'), ('', 'Unlisted')], default='', max_length=4),
            preserve_default=False,
        ),
        migrations.RunPython(forwards, backwards)
    ]
