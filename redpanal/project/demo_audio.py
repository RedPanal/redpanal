"""Small synthesized clips for the local demo (standard library only): something to listen to, not just a beep.

Every clip of a work lasts the same number of bars at the work's tempo, so the parts line up.
"""
import io
import math
import random
import struct
import wave

RATE = 22050
PROGRESSION = [("A", "minor"), ("F", "major"), ("C", "major"), ("G", "major")]
NOTES = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def freq(note, octave):
    return 440.0 * 2 ** ((NOTES[note] + 12 * (octave - 4)) / 12.0)


def chord(root, quality, octave):
    third = 3 if quality == "minor" else 4
    base = NOTES[root] + 12 * (octave - 4)
    return [440.0 * 2 ** ((base + i) / 12.0) for i in (0, third, 7)]


def beat_len(tempo):
    return 60.0 / tempo


def empty(tempo, bars):
    return [0.0] * int(RATE * beat_len(tempo) * 4 * bars)


def add(buf, start_s, samples, gain=1.0):
    i0 = int(start_s * RATE)
    for i, v in enumerate(samples):
        if 0 <= i0 + i < len(buf):
            buf[i0 + i] += v * gain


def pluck(f, seconds, brightness=0.5, rng=None):
    """Karplus-Strong plucked string."""
    rng = rng or random.Random(1)
    n = max(2, int(RATE / f))
    line = [rng.uniform(-1, 1) for _ in range(n)]
    out = []
    for i in range(int(seconds * RATE)):
        a = line[i % n]
        b = line[(i + 1) % n]
        line[i % n] = (a * (1 - brightness) + b * brightness) * 0.996
        out.append(a)
    return out


def tone(f, seconds, attack=0.01, decay=3.0, harmonics=(1.0,)):
    out = []
    for i in range(int(seconds * RATE)):
        t = i / RATE
        env = min(1.0, t / attack) * math.exp(-decay * t)
        out.append(env * sum(h * math.sin(2 * math.pi * f * (k + 1) * t) for k, h in enumerate(harmonics)))
    return out


def noise(seconds, decay, rng):
    return [rng.uniform(-1, 1) * math.exp(-decay * i / RATE) for i in range(int(seconds * RATE))]


def kick(rng):
    out, phase = [], 0.0
    for i in range(int(0.35 * RATE)):
        t = i / RATE
        phase += 2 * math.pi * (45 + 90 * math.exp(-30 * t)) / RATE
        out.append(math.sin(phase) * math.exp(-9 * t))
    return out


def drums(tempo, bars, style="rock"):
    rng, buf, b = random.Random(7), empty(tempo, bars), beat_len(tempo)
    k, sn = kick(rng), noise(0.2, 18, rng)
    for bar in range(bars):
        t0 = bar * 4 * b
        for beat in range(4):
            if style == "candombe":
                if beat in (0, 3) or (beat == 2 and bar % 2):
                    add(buf, t0 + beat * b, k, 0.9)
                for sixteenth in (0, 2, 3):
                    add(buf, t0 + beat * b + sixteenth * b / 4, noise(0.05, 60, rng), 0.25 if sixteenth else 0.4)
                if beat in (1, 3):
                    add(buf, t0 + beat * b + b / 2, sn, 0.35)
            else:
                if beat in (0, 2):
                    add(buf, t0 + beat * b, k, 0.9)
                if beat in (1, 3):
                    add(buf, t0 + beat * b, sn, 0.5)
                for half in (0, 1):
                    add(buf, t0 + beat * b + half * b / 2, noise(0.04, 80, rng), 0.18)
    return buf


def shaker(tempo, bars):
    rng, buf, b = random.Random(3), empty(tempo, bars), beat_len(tempo)
    for i in range(bars * 16):
        accent = 0.45 if i % 4 == 2 else 0.2
        add(buf, i * b / 4, noise(0.07, 45, rng), accent)
        if i % 8 == 6:  # güiro scrape
            scrape = [rng.uniform(-1, 1) * (0.5 + 0.5 * math.sin(2 * math.pi * 40 * j / RATE)) * math.exp(-8 * j / RATE)
                      for j in range(int(0.25 * RATE))]
            add(buf, i * b / 4, scrape, 0.25)
    return buf


def pad(tempo, bars, progression=PROGRESSION[:1]):
    buf, bar_s = empty(tempo, bars), beat_len(tempo) * 4
    for bar in range(bars):
        root, quality = progression[bar % len(progression)]
        for f in chord(root, quality, 3):
            for detune in (0.997, 1.003):
                add(buf, bar * bar_s, tone(f * detune, bar_s + 0.3, attack=0.6, decay=0.4, harmonics=(1, 0.3, 0.1)), 0.12)
    return buf


def bass(tempo, bars):
    rng, buf, b = random.Random(5), empty(tempo, bars), beat_len(tempo)
    for bar in range(bars):
        root, _ = PROGRESSION[bar % len(PROGRESSION)]
        f = freq(root, 2)
        for beat, mult in ((0, 1), (1.5, 1), (2, 1.5), (3, 2)):  # root, root, fifth, octave: a small walk
            add(buf, bar * 4 * b + beat * b, pluck(f * mult, b * 0.9, 0.3, rng), 0.7)
    return buf


def guitar(tempo, bars):
    rng, buf, b = random.Random(9), empty(tempo, bars), beat_len(tempo)
    for bar in range(bars):
        notes = chord(*PROGRESSION[bar % len(PROGRESSION)], 4)
        pattern = [notes[0] / 2, notes[1], notes[2], notes[1] * 2, notes[0], notes[2], notes[1], notes[2] / 2]
        for step, f in enumerate(pattern):
            add(buf, bar * 4 * b + step * b / 2, pluck(f, b * 1.5, 0.5, rng), 0.35)
    return buf


def synth(tempo, bars):
    buf, b = empty(tempo, bars), beat_len(tempo)
    prog = [("D", "minor"), ("A", "minor"), ("C", "major"), ("G", "major")]
    for bar in range(bars):
        notes = chord(*prog[bar % len(prog)], 4)
        for step in range(8):
            f = notes[step % 3] * (2 if step % 4 == 3 else 1)
            add(buf, bar * 4 * b + step * b / 2, tone(f, b * 0.6, attack=0.005, decay=6, harmonics=(1, 0.5, 0.33, 0.25)), 0.18)
    return buf


def to_wav(samples):
    peak = max(0.001, max(abs(s) for s in samples))
    scale = 0.85 * 32767 / peak
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * scale)) for s in samples))
    return out.getvalue()
