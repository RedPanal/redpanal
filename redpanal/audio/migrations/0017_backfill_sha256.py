import hashlib

from django.core.files.storage import default_storage
from django.db import migrations


def backfill(apps, schema_editor):
    """Fingerprint existing files so re-uploads of them are recognised."""
    Audio = apps.get_model('audio', 'Audio')
    missing = 0
    for audio in Audio.objects.filter(sha256="").exclude(audio="").iterator():
        if not default_storage.exists(audio.audio.name):
            missing += 1
            continue
        digest = hashlib.sha256()
        with default_storage.open(audio.audio.name, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        Audio.objects.filter(pk=audio.pk).update(sha256=digest.hexdigest())
    if missing:
        print("\n  audio: %d files not found in storage; they have no fingerprint." % missing)


class Migration(migrations.Migration):

    dependencies = [
        ('audio', '0016_audio_source_sha256'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
