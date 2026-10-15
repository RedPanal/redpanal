"""Add a whole studio folder to a work: stems as aligned parts, session files as attachments.

Works like a commit: identical files are skipped, a new take of a stem with the
same file name replaces the previous one (kept as an alternative), and nothing
is stored twice for the same person.
"""
import hashlib
import os
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from actstream import action

from audio.models import Audio
from audio.uploads import ACCEPTED_EXTENSIONS, prepare_audio_file
from redpanal.utils.helpers import get_file_extension
from .models import (Attachment, Contribution, ATTACHMENT_EXTENSIONS, attachment_kind,
                     VISIBILITY_PUBLIC, guess_alignment)

# Words that usually appear in stem file names, by instrument code.
INSTRUMENT_HINTS = [
    ("electric guitar", r"(elec|eg|electric).?(gtr|guit)|guit.*elec"),
    ("bass", r"\b(bass|bajo|bjo|bs)\b|bass|bajo"),
    ("drums", r"drum|bater|bombo|kick|snare|redo|hat|tom|kit|overhead|\boh\b"),
    ("voice", r"vox|voc|voz|voice|coro|choir|lead|bgv|canto"),
    ("guitar", r"gtr|guit|guitarra|acoust"),
    ("piano", r"piano|pno"),
    ("sinthesizer", r"synth|sint|pad|arp"),
    ("strings", r"string|cuerda|cello|viola"),
    ("violin", r"viol[ií]n|violin|vln"),
    ("brass", r"brass|trump|tromp|trombon|horn|bronce|metal"),
    ("woodwind", r"flute|flauta|clarin|oboe|madera"),
    ("saxophone", r"\bsax"),
]


def guess_instrument(filename):
    name = os.path.splitext(os.path.basename(filename))[0].lower().replace("_", " ").replace("-", " ")
    for code, pattern in INSTRUMENT_HINTS:
        if re.search(pattern, name):
            return code
    return "other"


def file_sha256(f):
    digest = hashlib.sha256()
    for chunk in f.chunks():
        digest.update(chunk)
    f.seek(0)
    return digest.hexdigest()


def usage_bytes(user):
    """Space this person uses: their audio files plus the session files they uploaded."""
    audio = Audio.objects.filter(user=user).aggregate(total=Sum("size"))["total"] or 0
    files = Attachment.objects.filter(uploaded_by=user).aggregate(total=Sum("size"))["total"] or 0
    return audio + files


def quota_bytes():
    return settings.RP_USER_QUOTA_MB * 1024 * 1024


class StemsResult(object):
    def __init__(self):
        self.added, self.replaced, self.unchanged = [], [], []
        self.attachments, self.attachments_unchanged = [], []
        self.errors = []
        self.version = None

    @property
    def changed(self):
        return bool(self.added or self.attachments)


def classify(files):
    """Split uploads into audio stems, session attachments and files we don't take."""
    audio, attachments, rejected = [], [], []
    for f in files:
        ext = get_file_extension(f.name)
        if ext in ACCEPTED_EXTENSIONS:
            audio.append(f)
        elif ext in ATTACHMENT_EXTENSIONS:
            attachments.append(f)
        else:
            rejected.append(f)
    return audio, attachments, rejected


def add_stems(project, user, files, instruments=None, note="", accept_terms=False):
    """Add stems and session files to a work. Returns a StemsResult."""
    result = StemsResult()
    is_owner = user == project.user
    audio_files, attachment_files, rejected = classify(files)
    for f in rejected:
        result.errors.append(_("«%s» is not an audio or session file RedPanal knows.") % f.name)
    if not is_owner and not accept_terms:
        result.errors.append(_("Accept the license agreement to contribute."))
        return result

    incoming = sum(f.size for f in audio_files + attachment_files)
    if usage_bytes(user) + incoming > quota_bytes():
        result.errors.append(_("Not enough space: you use %(used)d MB of %(total)d MB.") % {
            "used": usage_bytes(user) // (1024 * 1024), "total": settings.RP_USER_QUOTA_MB})
        return result
    max_attachment = settings.RP_ATTACHMENT_MAX_MB * 1024 * 1024

    instruments = list(instruments or [])
    names = [f.name for f in files]
    first_contribution = None
    now = timezone.now()

    with transaction.atomic():
        project.first_version()
        new_audios = []
        new_contributions = []
        for f in audio_files:
            index = names.index(f.name)
            instrument = (instruments[index] if index < len(instruments) and instruments[index]
                          else guess_instrument(f.name))
            digest = file_sha256(f)
            same_file = Q(audio__sha256=digest) | Q(audio__source_sha256=digest)
            in_work = project.contributions.exclude(status=Contribution.WITHDRAWN).filter(same_file)
            if in_work.exists():
                result.unchanged.append(f.name)
                continue

            audio = Audio.objects.filter(Q(sha256=digest) | Q(source_sha256=digest), user=user).first()
            if audio is None:
                audio = Audio(user=user, audio=prepare_audio_file(f),
                              name="%s · %s" % (project.name, os.path.splitext(f.name)[0]),
                              instrument=instrument, tempo=project.tempo, license=project.license)
                audio._part_of_work = True
                audio.save()
                Audio.objects.filter(pk=audio.pk).update(source_sha256=digest)
            new_audios.append((f, audio))

        # Second pass: with every duration of the batch known, guess which stems line up.
        batch_durations = [a.get_duration() for _, a in new_audios]
        for f, audio in new_audios:
            previous = (project.contributions.filter(status=Contribution.INCLUDED, source_filename=f.name)
                        .exclude(audio=audio).first())
            # Someone else's stems go into the version they make: nobody has to approve them.
            status = Contribution.INCLUDED if is_owner else Contribution.VERSIONED
            contribution, created = Contribution.objects.get_or_create(
                project=project, audio=audio,
                defaults={"contributor": user, "note": note, "offset_ms": 0, "status": status,
                          "source_filename": f.name, "terms_accepted_at": now,
                          "alignment": guess_alignment(project, audio, batch_durations)})
            if not created:  # the same file had been withdrawn: bring it back
                contribution.terms_accepted_at = now
                contribution.save(update_fields=["terms_accepted_at"])
                contribution.set_status(status)
            if is_owner:
                project.audios.add(audio)
                if previous is not None:
                    previous.set_status(Contribution.ALTERNATIVE)
                    result.replaced.append(f.name)
                else:
                    result.added.append(f.name)
            else:
                result.added.append(f.name)
            first_contribution = first_contribution or contribution
            new_contributions.append(contribution)

        for f in attachment_files:
            if f.size > max_attachment:
                result.errors.append(_("«%(name)s» is bigger than %(mb)d MB.") % {
                    "name": f.name, "mb": settings.RP_ATTACHMENT_MAX_MB})
                continue
            digest = file_sha256(f)
            current = project.attachments.filter(replaced=False)
            if current.filter(sha256=digest).exists():
                result.attachments_unchanged.append(f.name)
                continue
            current.filter(name=f.name).update(replaced=True)
            Attachment.objects.create(project=project, uploaded_by=user, file=f, name=f.name,
                                      kind=attachment_kind(f.name), size=f.size, sha256=digest)
            result.attachments.append(f.name)

    if new_contributions:
        result.version = project.new_version(user, new_contributions, message=note)
    if result.added or result.replaced:
        project.refresh_preview()
        project.reindex_search()
    if first_contribution is not None and not is_owner:
        action.send(user, verb='contributed', action_object=first_contribution, target=project,
                    public=project.visibility == VISIBILITY_PUBLIC)
    return result
