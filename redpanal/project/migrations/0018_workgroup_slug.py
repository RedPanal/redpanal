from django.db import migrations, models


def fill_slugs(apps, schema_editor):
    from project.models import group_slug
    WorkGroup = apps.get_model("project", "WorkGroup")
    for group in WorkGroup.objects.order_by("pk"):
        group.slug = group_slug(group.name, WorkGroup.objects.exclude(pk=group.pk).exclude(slug=""))
        group.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("project", "0017_versions_by_anyone"),
    ]

    operations = [
        migrations.AddField(
            model_name="workgroup",
            name="slug",
            field=models.SlugField(max_length=110, default="", blank=True),
            preserve_default=False,
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="workgroup",
            name="slug",
            field=models.SlugField(max_length=110, unique=True),
        ),
    ]
