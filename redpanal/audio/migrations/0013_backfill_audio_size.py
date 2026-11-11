from django.core.files.storage import default_storage
from django.db import migrations


def backfill(apps, schema_editor):
    """Record the size of existing files so storage quotas count them."""
    Audio = apps.get_model('audio', 'Audio')
    missing = 0
    for audio in Audio.objects.filter(size__isnull=True).exclude(audio="").iterator():
        # Through the storage, so it works with any backend; a missing file is reported, not hidden.
        if default_storage.exists(audio.audio.name):
            Audio.objects.filter(pk=audio.pk).update(size=default_storage.size(audio.audio.name))
        else:
            missing += 1
    if missing:
        print("\n  audio: %d files not found in storage; their size stays unknown." % missing)


class Migration(migrations.Migration):

    dependencies = [
        ('audio', '0012_audio_size_alter_audio_sha256'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
