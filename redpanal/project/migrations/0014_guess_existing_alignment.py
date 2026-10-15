from django.db import migrations


def duration_ms(audio):
    if audio.samplerate and audio.totalframes:
        return audio.totalframes / float(audio.samplerate) * 1000
    return None


def matches(a, b):
    return bool(a and b) and abs(a - b) <= max(60, 0.005 * max(a, b))


def forwards(apps, schema_editor):
    """Older works: the oldest part sets the timeline; equal-length parts or parts someone
    already shifted by hand are aligned; the rest play on their own until aligned."""
    Project = apps.get_model('project', 'Project')
    Contribution = apps.get_model('project', 'Contribution')
    for project in Project.objects.all().iterator():
        parts = list(Contribution.objects.filter(project=project).select_related("audio").order_by("created_at"))
        if not parts:
            continue
        reference = next((p for p in parts if p.status == "included"), parts[0])
        ref_ms = duration_ms(reference.audio)
        for p in parts:
            aligned = p.pk == reference.pk or p.offset_ms != 0 or matches(duration_ms(p.audio), ref_ms)
            Contribution.objects.filter(pk=p.pk).update(alignment="aligned" if aligned else "pending")


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0013_contribution_alignment'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
