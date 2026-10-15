import os

from django.conf import settings
from django.db import migrations


def backfill(apps, schema_editor):
    """Record the size of existing files so storage quotas count them."""
    Audio = apps.get_model('audio', 'Audio')
    for audio in Audio.objects.filter(size__isnull=True).exclude(audio="").iterator():
        path = os.path.join(settings.MEDIA_ROOT, audio.audio.name)
        if os.path.exists(path):
            Audio.objects.filter(pk=audio.pk).update(size=os.path.getsize(path))


class Migration(migrations.Migration):

    dependencies = [
        ('audio', '0012_audio_size_alter_audio_sha256'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
