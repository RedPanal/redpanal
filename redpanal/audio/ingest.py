"""One rule for every way audio enters RedPanal: format, size, space, conversion, fingerprint.

Uploading must be as easy as possible: only the file is needed. The name comes from the file
name and the instrument and type are guessed from it; the person can complete them later.
"""
import hashlib
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext as _

from .models import Audio, VISIBILITY_PRIVATE
from .uploads import prepare_audio_file

# Bits of a file name that say nothing about the sound: track numbers, takes, "final", versions.
NOISE = re.compile(r"^\s*\d{1,3}\s*[-_. ]+|\b(final|definitivo|bounce|export|v\d+|take\s*\d+|toma\s*\d+)\b",
                   re.IGNORECASE)
TYPE_HINTS = [
    ("master", r"\bmaster\b|\bmastering\b"),
    ("mix", r"\bmix\b|\bmezcla\b|\bpremix\b"),
    ("loop", r"\bloop\b|\blp\b"),
    ("demo", r"\bdemo\b|\bboceto\b|\bidea\b|\bmaqueta\b"),
    ("sample", r"\bsample\b|\bone.?shot\b|\bhit\b"),
]


def clean_name(filename):
    """«02_bajo_final_v3.wav» → «Bajo»."""
    name = os.path.splitext(os.path.basename(filename))[0].replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", NOISE.sub(" ", name)).strip(" .")
    return (name[:1].upper() + name[1:])[:100] if name else _("Untitled")


def guess_type(filename):
    name = os.path.splitext(os.path.basename(filename))[0].lower().replace("_", " ").replace("-", " ")
    for code, pattern in TYPE_HINTS:
        if re.search(pattern, name):
            return code
    return "track"


def file_sha256(f):
    digest = hashlib.sha256()
    for chunk in f.chunks():
        digest.update(chunk)
    f.seek(0)
    return digest.hexdigest()


def check(user, f):
    """Raise ValidationError if this file can't come in: format, size, the person's space."""
    from project.forms import clean_audio_upload
    from project.stems import usage_bytes, quota_bytes
    clean_audio_upload(f)
    if usage_bytes(user) + f.size > quota_bytes():
        raise ValidationError(_("Not enough space: you use %(used)d MB of %(total)d MB.") % {
            "used": usage_bytes(user) // (1024 * 1024), "total": settings.RP_USER_QUOTA_MB})


def ingest(user, f, name=None, private=True, part_of_work=False, **fields):
    """Store an uploaded or recorded file as a sound of `user`, with everything guessed.

    The same file uploaded again by the same person gives back the sound they already have.
    """
    from project.stems import guess_instrument
    check(user, f)
    digest = file_sha256(f)
    existing = Audio.objects.filter(Q(sha256=digest) | Q(source_sha256=digest), user=user).first()
    if existing is not None:
        return existing
    instrument = guess_instrument(f.name)
    audio = Audio(user=user, audio=prepare_audio_file(f), name=name or clean_name(f.name),
                  instrument="" if instrument == "other" else instrument, use_type=guess_type(f.name),
                  needs_details=True, **fields)
    if private:
        audio.visibility = VISIBILITY_PRIVATE
    audio._part_of_work = part_of_work
    audio.save()
    Audio.objects.filter(pk=audio.pk).update(source_sha256=digest)
    return audio
