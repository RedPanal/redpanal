"""Make the waveform files (.json) of sounds that don't have them.

Before 3.0 the waveform was an image (.png) made on upload; the players now read the peaks
from <file>.json and <file>.big.json. Sounds uploaded before the change have no such files,
so their waveform is empty. Run once after deploying 3.x:

    python manage.py build_waveforms

It skips sounds that already have both files, so it can be stopped and run again.
"""
import os

from django.core.management.base import BaseCommand
from pydub.exceptions import CouldntDecodeError

from audio.models import Audio, save_waveforms


class Command(BaseCommand):
    help = "Build the waveform (.json) of every sound that doesn't have one."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Rebuild every waveform, also the existing ones.")
        parser.add_argument("--remove-png", action="store_true",
                            help="Delete the old .png / .big.png waveform images once the new files exist.")

    def handle(self, *args, **options):
        built = skipped = missing = failed = removed = 0
        for audio in Audio.objects.exclude(audio="").order_by("pk").iterator():
            try:
                path = audio.audio.path
            except (ValueError, NotImplementedError):
                missing += 1
                continue
            if not os.path.exists(path):
                missing += 1
                continue
            has_both = os.path.exists(path + ".json") and os.path.exists(path + ".big.json")
            if has_both and not options["all"]:
                skipped += 1
            else:
                try:
                    sound = save_waveforms(audio)
                    built += 1
                except (CouldntDecodeError, OSError, IndexError, ValueError) as e:
                    failed += 1
                    self.stderr.write("could not read %s (sound %d): %s" % (audio.audio.name, audio.pk, e))
                    continue
                # Sounds whose processing never finished have no duration either.
                if not audio.samplerate:
                    Audio.objects.filter(pk=audio.pk).update(
                        channels=sound.channels, blocksize=0, samplerate=sound.frame_rate,
                        totalframes=sound.frame_count())
            if options["remove_png"]:
                for suffix in (".png", ".big.png"):
                    if os.path.exists(path + suffix):
                        os.remove(path + suffix)
                        removed += 1
        self.stdout.write("Waveforms built: %d. Already there: %d. File missing: %d. Could not be read: %d.%s" % (
            built, skipped, missing, failed, (" Old images removed: %d." % removed) if options["remove_png"] else ""))
