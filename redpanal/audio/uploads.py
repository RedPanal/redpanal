"""Prepare uploaded or browser-recorded audio before storing it."""
import io
import os

from django.core.files.base import ContentFile
from pydub import AudioSegment

from redpanal.utils.helpers import get_file_extension

# Formats every browser can play: stored as they come.
PLAYABLE_EXTENSIONS = ["mp3", "ogg", "oga", "flac", "wav"]
# Phone voice notes and browser recordings: converted to mp3.
CONVERTED_EXTENSIONS = ["webm", "weba", "m4a", "mp4", "aac", "opus"]
ACCEPTED_EXTENSIONS = PLAYABLE_EXTENSIONS + CONVERTED_EXTENSIONS


def prepare_audio_file(uploaded, trim_start_ms=None, trim_end_ms=None):
    """Return a file ready to save in Audio.audio.

    Converts non playable formats to mp3 and applies an optional trim.
    """
    ext = get_file_extension(uploaded.name)
    trim = bool(trim_start_ms) or trim_end_ms is not None
    if ext in PLAYABLE_EXTENSIONS and not trim:
        return uploaded

    uploaded.seek(0)
    # ffmpeg probes the real container: the extension a browser or phone gives is not reliable.
    sound = AudioSegment.from_file(uploaded, format=None)
    if trim:
        start = max(0, int(trim_start_ms or 0))
        end = len(sound) if trim_end_ms is None else min(len(sound), int(trim_end_ms))
        if end > start:
            sound = sound[start:end]

    out = io.BytesIO()
    sound.export(out, format="mp3", bitrate="192k")
    base = os.path.splitext(os.path.basename(uploaded.name))[0] or "grabacion"
    return ContentFile(out.getvalue(), name=base + ".mp3")
