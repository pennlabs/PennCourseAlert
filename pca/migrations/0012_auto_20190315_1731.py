# Generated by Django 2.1.7 on 2019-03-15 17:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pca', '0011_auto_20190315_1642'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courseupdate',
            name='new_status',
            field=models.CharField(choices=[('O', 'Open'), ('C', 'Closed'), ('X', 'Cancelled')], max_length=16),
        ),
        migrations.AlterField(
            model_name='courseupdate',
            name='old_status',
            field=models.CharField(choices=[('O', 'Open'), ('C', 'Closed'), ('X', 'Cancelled')], max_length=16),
        ),
    ]
