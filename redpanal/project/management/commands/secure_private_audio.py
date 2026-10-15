"""Move the audio of works that aren't public to addresses that can't be guessed.

Uploads made before the privacy changes live at uploads/audios/YYYY_MM/<name>,
which anyone could guess. Run once after deploying:

    python manage.py secure_private_audio
"""
from django.core.management.base import BaseCommand

from project.models import Project, VISIBILITY_PUBLIC


class Command(BaseCommand):
    help = "Give the audio files of non public works a random folder."

    def handle(self, *args, **options):
        moved = 0
        for project in Project.objects.exclude(visibility=VISIBILITY_PUBLIC):
            for contribution in project.contributions.select_related("audio"):
                if contribution.audio.move_to_private_path():
                    moved += 1
        self.stdout.write(self.style.SUCCESS("Moved %d files." % moved))
