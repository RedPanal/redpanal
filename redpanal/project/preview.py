"""Short, low quality excerpt of a work, for open calls."""
import io
import logging

from django.core.files.base import ContentFile
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

logger = logging.getLogger(__name__)


MARK_EVERY_MS = 10000


def _beep(freq=1320, ms=90, rate=44100, gain_db=-24):
    # pydub 0.16's generators break on Python 3.11 (array.tostring), so build the tone directly.
    import array
    import math
    amplitude = 32767 * 10 ** (gain_db / 20)
    samples = array.array("h", (int(amplitude * math.sin(2 * math.pi * freq * i / rate))
                                for i in range(int(rate * ms / 1000))))
    return AudioSegment(data=samples.tobytes(), sample_width=2, frame_rate=rate, channels=1)


def add_sound_mark(excerpt):
    """Two soft beeps every 10 seconds: audible, not ruinous."""
    beep = _beep().fade_in(10).fade_out(40)
    mark = beep + AudioSegment.silent(duration=70, frame_rate=44100) + beep
    for position in range(5000, len(excerpt), MARK_EVERY_MS):
        excerpt = excerpt.overlay(mark, position=position)
    return excerpt


def preview_peaks(segment, bars=200):
    """Waveform of the excerpt, in the format the players read: {"peaks": [0..1], "duration": s}."""
    step = max(1, len(segment) // bars)
    levels = [segment[i * step:(i + 1) * step].rms for i in range(bars)]
    top = max(levels) or 1
    return {"peaks": [round(v / top, 3) for v in levels], "duration": len(segment) / 1000.0}


def mix_parts(parts):
    """Overlay parts at their offsets. Returns (mix, origin_ms), or (None, 0) if nothing could be read."""
    tracks = []
    for part in parts:
        try:
            tracks.append((part.offset_ms, AudioSegment.from_file(part.audio.audio.path)))
        except (CouldntDecodeError, FileNotFoundError, OSError):
            logger.exception("mix: could not read %s", part.audio.audio.name)
    if not tracks:
        return None, 0

    origin = min(0, min(offset for offset, _ in tracks))
    length = max(offset - origin + len(sound) for offset, sound in tracks)
    channels = max(sound.channels for _, sound in tracks)
    mix = AudioSegment.silent(duration=length, frame_rate=44100).set_channels(channels)
    for offset, sound in tracks:
        mix = mix.overlay(sound.set_frame_rate(44100).set_channels(channels), position=offset - origin)
    return mix, origin


def build_preview(project, seconds=None):
    """Mix the included parts with their offsets and cut an excerpt.

    Mono, 64 kbps, with short fades: enough to decide whether to ask to join,
    not a usable copy of the work.
    """
    from .models import PREVIEW_SECONDS
    seconds = seconds or PREVIEW_SECONDS
    parts = list(project.aligned_parts())  # loose parts would make a mess of the excerpt
    if not parts:
        return None
    mix, origin = mix_parts(parts)
    if mix is None:
        return None

    start = min(project.preview_start_ms - origin, max(0, len(mix) - 1))
    excerpt = mix[start:start + seconds * 1000].set_channels(1)
    fade = min(1000, len(excerpt) // 4)
    excerpt = excerpt.fade_in(fade).fade_out(fade)
    if project.preview_watermark:
        excerpt = add_sound_mark(excerpt)

    out = io.BytesIO()
    excerpt.export(out, format="mp3", bitrate="64k")
    content = ContentFile(out.getvalue())
    content.peaks = preview_peaks(excerpt)
    return content
