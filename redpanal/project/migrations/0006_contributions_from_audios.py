from django.db import migrations


def forwards(apps, schema_editor):
    """Existing works keep every audio they had, now as included parts."""
    Project = apps.get_model('project', 'Project')
    Contribution = apps.get_model('project', 'Contribution')
    for project in Project.objects.all().iterator():
        if project.status == 'idea':
            project.status = 'in_progress'
            project.save(update_fields=['status'])
        for audio in project.audios.all():
            Contribution.objects.get_or_create(
                project=project, audio=audio,
                defaults={'contributor_id': audio.user_id, 'status': 'included'},
            )


def backwards(apps, schema_editor):
    # project.audios is kept in sync, so dropping the contributions loses nothing.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0005_project_license_project_musical_key_project_status_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
