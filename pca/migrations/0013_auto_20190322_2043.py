# Generated by Django 2.1.7 on 2019-03-22 20:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pca', '0012_auto_20190315_1731'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courseupdate',
            name='new_status',
            field=models.CharField(choices=[('O', 'Open'), ('C', 'Closed'), ('X', 'Cancelled'), ('', 'Unlisted')], max_length=16),
        ),
        migrations.AlterField(
            model_name='courseupdate',
            name='old_status',
            field=models.CharField(choices=[('O', 'Open'), ('C', 'Closed'), ('X', 'Cancelled'), ('', 'Unlisted')], max_length=16),
        ),
        migrations.AlterField(
            model_name='registration',
            name='notification_sent_by',
            field=models.CharField(blank=True, choices=[('', 'Unsent'), ('LEG', '[Legacy] Sequence of course API requests'), ('WEB', 'Webhook'), ('SERV', 'Course Status Service'), ('ADM', 'Admin Interface')], default='', max_length=16),
        ),
    ]
