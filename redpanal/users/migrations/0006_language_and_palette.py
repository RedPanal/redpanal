from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_profile_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="language",
            field=models.CharField(blank=True, default="", max_length=8, verbose_name="language"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="palette",
            field=models.CharField(choices=[("moderna", "Modern: cyan and mint"), ("neon", "Neon: dark, for the night"),
                                            ("calida", "Warm: sand and terracotta"),
                                            ("lavanda", "Lavender: soft pastels")],
                                   default="moderna", max_length=16, verbose_name="colors"),
        ),
    ]
