"""Demo data for local development: two people, a work with requests and a pending contribution.

    python manage.py seed_demo

Only for a local development database: the demo accounts share a known password.
"""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from audio.models import Audio
from project import demo_audio
from project.models import (Project, PartRequest, Contribution, Membership,
                            VISIBILITY_OPEN_CALL, VISIBILITY_PRIVATE)

DEMO_PASSWORD = "redpanal-demo"
DEMO_USERS = {
    "lucia_demo": {"realname": "Lucía Ferreyra", "instruments": ["guitar", "voice"], "location": "Rosario",
                   "genres": "zamba, canción", "tools": "celular", "open": True},
    "tincho_demo": {"realname": "Tincho Acosta", "instruments": ["bass", "sinthesizer"], "location": "Lanús",
                    "genres": "cumbia, electrónica, candombe", "tools": "Ableton, REAPER", "open": True},
    # Quick local access: user "demo", password "demo". Never on a real server (DEBUG only).
    "demo": {"realname": "Demo", "instruments": ["voice", "drums"], "password": "demo", "location": "Córdoba"},
}
# Each demo audio, synthesized: (generator, tempo, bars). Parts of the same work share tempo and length.
CLIPS = {
    "Candombe chico 100": (lambda: demo_audio.drums(100, 4, "candombe")),
    "Shaker y güiro": (lambda: demo_audio.shaker(104, 4)),
    "Pad en La menor": (lambda: demo_audio.pad(92, 4)),
    "Lluvia en Pichincha · voz y guitarra": (lambda: demo_audio.guitar(92, 8)),
    "Lluvia en Pichincha · bajo": (lambda: demo_audio.bass(92, 8)),
    "Madrugada · sintes": (lambda: demo_audio.synth(100, 8)),
}


def clip(name):
    return ContentFile(demo_audio.to_wav(CLIPS[name]()), name=slugify(name) + ".wav")


class Command(BaseCommand):
    help = "Create demo users and a work to try the collaboration flows locally."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG = True.")

        users = {}
        for username, data in DEMO_USERS.items():
            user, created = User.objects.get_or_create(username=username, defaults={"email": "%s@example.test" % username})
            if created:
                user.set_password(data.get("password", DEMO_PASSWORD))
                user.save()
            profile = user.userprofile
            profile.realname = data["realname"]
            profile.instruments = data["instruments"]
            profile.location = data.get("location", "")
            profile.genres = data.get("genres", "")
            profile.tools = data.get("tools", "")
            profile.open_to_collaborate = data.get("open", False)
            profile.save()
            users[username] = user

        lucia, tincho, demo = users["lucia_demo"], users["tincho_demo"], users["demo"]

        # Loose sounds for Explore › Sounds (idempotent).
        sounds = [("Candombe chico 100", "loop", "drums", 100, ""),
                  ("Shaker y güiro", "loop", "drums", 104, ""),
                  ("Pad en La menor", "sample", "sinthesizer", 92, "Am")]
        for name, use_type, instrument, tempo, key in sounds:
            if not Audio.objects.filter(user=tincho, name=name).exists():
                a = Audio(user=tincho, name=name, use_type=use_type, instrument=instrument,
                          tempo=tempo, musical_key=key)
                c = clip(name)
                a.audio.save(c.name, c, save=True)

        if Project.objects.filter(user=lucia, name="Lluvia en Pichincha").exists():
            self.replace_beeps()
            self.give_demo_access(demo)
            self.stdout.write("Demo data already there.")
            return

        def audio(user, name, instrument):
            a = Audio(user=user, name=name, instrument=instrument)
            c = clip(name)
            a.audio.save(c.name, c, save=True)
            return a

        work = Project.objects.create(user=lucia, name="Lluvia en Pichincha", status="idea", tempo=92)
        guitar = audio(lucia, "Lluvia en Pichincha · voz y guitarra", "guitar")
        Contribution.objects.create(project=work, audio=guitar, contributor=lucia, status=Contribution.INCLUDED)
        work.audios.add(guitar)
        bass = PartRequest.objects.create(project=work, instrument="bass", description="un bajo tranqui")
        PartRequest.objects.create(project=work, instrument="drums", description="batería con escobillas")

        bass_audio = audio(tincho, "Lluvia en Pichincha · bajo", "bass")
        Contribution.objects.create(project=work, audio=bass_audio, contributor=tincho, request=bass,
                                    note="Probé algo con walking, si no va lo cambio", offset_ms=250)

        other = Project.objects.create(user=tincho, name="Madrugada", status="in_progress", tempo=100)
        synth = audio(tincho, "Madrugada · sintes", "sinthesizer")
        Contribution.objects.create(project=other, audio=synth, contributor=tincho, status=Contribution.INCLUDED)
        other.audios.add(synth)
        PartRequest.objects.create(project=other, instrument="voice", description="segunda voz")

        # Privacy stages: an open call (Tincho already joined) and a private work.
        Membership.objects.create(project=work, user=tincho, status=Membership.ACTIVE)
        work.set_visibility(VISIBILITY_OPEN_CALL)
        other.set_visibility(VISIBILITY_PRIVATE)
        self.give_demo_access(demo)

        self.stdout.write(self.style.SUCCESS("Demo data created: users %s." % ", ".join(DEMO_USERS)))

    def replace_beeps(self):
        """Older demo databases used 0.2 s test tones: swap them for the synthesized clips."""
        replaced = 0
        for audio in Audio.objects.filter(name__in=CLIPS, user__username__in=DEMO_USERS):
            if (audio.get_duration() or 0) < 1000:
                c = clip(audio.name)
                audio.audio.save(c.name, c, save=True)
                replaced += 1
        if replaced:
            for project in Project.objects.filter(name__in=["Lluvia en Pichincha", "Madrugada"]):
                project.refresh_preview()
            self.stdout.write("Replaced %d test tones with demo clips." % replaced)

    def give_demo_access(self, demo):
        """The "demo" account joins the example works, to see every access level from inside."""
        for project in Project.objects.filter(name__in=["Lluvia en Pichincha", "Madrugada"]):
            Membership.objects.get_or_create(project=project, user=demo, defaults={"status": Membership.ACTIVE})
