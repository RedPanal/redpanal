"""SEC-12: the cached HTML of comments was built without escaping names and addresses.

Clear it so every comment is rendered again, safely, the next time it's shown.
"""
from django.db import migrations


def clear_cache(apps, schema_editor):
    apps.get_model("social", "Message").objects.update(_msg_html_cache=None)


class Migration(migrations.Migration):

    dependencies = [("social", "0006_reactions")]

    operations = [migrations.RunPython(clear_cache, migrations.RunPython.noop)]
