# Generated by Django 2.2.12 on 2020-05-20 01:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0003_auto_20200511_2150'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='image',
            field=models.ImageField(blank=True, max_length=150, null=True, upload_to='uploads/images/projects/%Y_%m', verbose_name='image'),
        ),
    ]
