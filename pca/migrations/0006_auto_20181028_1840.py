# Generated by Django 2.1.2 on 2018-10-28 18:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pca', '0005_section_is_open_updated_at'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='registration',
            name='emails',
        ),
        migrations.AddField(
            model_name='registration',
            name='email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.DeleteModel(
            name='Email',
        ),
    ]