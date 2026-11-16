"""Read audio files with pydub, including the ones pydub can't read on its own.

When the source is 24-bit (a common FLAC export), ffmpeg writes the intermediate
WAV with a ``WAVE_FORMAT_EXTENSIBLE`` header (format tag 0xFFFE). Python's
``wave`` module, which pydub uses to parse that file, only understands plain PCM
before Python 3.12, so ``AudioSegment.from_file`` dies with
``wave.Error: unknown format: 65534``.

The fallback here re-decodes the file to 16-bit PCM and rewrites the header tag,
which is more than enough for waveforms, mixes and previews.
"""
import os
import struct
import subprocess
import tempfile
import wave

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

WAVE_FORMAT_PCM = 1
WAVE_FORMAT_EXTENSIBLE = 0xFFFE


def _plain_wav_bytes(path):
    """Decode ``path`` to a 16-bit PCM WAV and return its bytes."""
    command = [AudioSegment.converter, "-y", "-i", path, "-vn",
               "-acodec", "pcm_s16le", "-f", "wav", "-"]
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise CouldntDecodeError(process.stderr.decode("utf-8", "replace"))
    return _as_plain_pcm(process.stdout)


def _as_plain_pcm(data):
    """Rewrite a WAVE_FORMAT_EXTENSIBLE header so Python's ``wave`` accepts it.

    The samples of an extensible WAV whose sub-format is PCM are ordinary PCM,
    so only the format tag needs fixing.
    """
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset:offset + 4]
        size = struct.unpack_from("<I", data, offset + 4)[0]
        if chunk_id == b"fmt " and size >= 2:
            tag = struct.unpack_from("<H", data, offset + 8)[0]
            if tag == WAVE_FORMAT_EXTENSIBLE:
                data = data[:offset + 8] + struct.pack("<H", WAVE_FORMAT_PCM) + data[offset + 10:]
            break
        offset += 8 + size + (size & 1)
    return data


def _decode_plain_pcm(path):
    return AudioSegment(data=_plain_wav_bytes(path))


def _temporary_copy(source):
    """Write a file-like ``source`` to a temporary file. Returns (path, cleanup)."""
    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "wb") as out:
            if hasattr(source, "seek"):
                source.seek(0)
            out.write(source.read())
    except Exception:
        os.remove(path)
        raise
    return path, path


def load_audio(source):
    """Like ``AudioSegment.from_file(source)``, but able to read 24-bit audio too.

    ``source`` may be a filesystem path or an open (seekable) file object.
    """
    if isinstance(source, (str, os.PathLike)):
        path, cleanup = source, None
    else:
        path, cleanup = _temporary_copy(source)
    try:
        try:
            return AudioSegment.from_file(path)
        except wave.Error:
            return _decode_plain_pcm(path)
    finally:
        if cleanup:
            os.remove(cleanup)
