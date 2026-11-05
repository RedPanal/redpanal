import hashlib
import os

from django.conf import settings
from django.db import migrations


def backfill(apps, schema_editor):
    """Fingerprint existing files so re-uploads of them are recognised."""
    Audio = apps.get_model('audio', 'Audio')
    for audio in Audio.objects.filter(sha256="").exclude(audio="").iterator():
        path = os.path.join(settings.MEDIA_ROOT, audio.audio.name)
        if not os.path.exists(path):
            continue
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        Audio.objects.filter(pk=audio.pk).update(sha256=digest.hexdigest())


class Migration(migrations.Migration):

    dependencies = [
        ('audio', '0016_audio_source_sha256'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
