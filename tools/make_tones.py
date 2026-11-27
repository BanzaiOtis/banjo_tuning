"""Generate the plucked-string sound files the app plays (src/assets/tones/nNN.wav).

You only need to run this again if you want to change the sound (takes ~20 s):
    python tools/make_tones.py

Each note is built by "additive synthesis": a stack of sine waves at the note's
harmonics (1x, 2x, 3x... the pitch). Each harmonic starts loud and fades away,
higher ones faster, which is roughly what a plucked banjo string does. Tweak the
settings below and re-run to change the character of the sound.
"""
import math
import os
import struct
import wave

SAMPLE_RATE = 44100   # CD standard; phones play this without converting (22050 played flat on Android)
DURATION = 1.4          # seconds
LOWEST, HIGHEST = 33, 109  # MIDI range (A1..C#8): any tuning, 25 frets, transposed up to ±12
PLUCK_POINT = 0.12      # where the string is picked (0-0.5); nearer 0 = brighter, twangier
MAX_HARMONICS = 14
BASE_DECAY = 2.2        # how fast the note fades (per second); bigger = shorter, more banjo-like
HIGH_DECAY = 0.0025     # extra fade for higher harmonics
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "assets", "tones")


def pluck(midi: int) -> list[float]:
    freq = 440.0 * 2 ** ((midi - 69) / 12)
    partials = []
    for k in range(1, MAX_HARMONICS + 1):
        fk = k * freq
        if fk > SAMPLE_RATE * 0.45:      # stay below the highest frequency a file can hold
            break
        amp = abs(math.sin(math.pi * k * PLUCK_POINT)) / k ** 0.9
        decay = BASE_DECAY + HIGH_DECAY * fk
        partials.append((2 * math.pi * fk / SAMPLE_RATE, amp, math.exp(-decay / SAMPLE_RATE)))

    total = int(SAMPLE_RATE * DURATION)
    out = [0.0] * total
    for step, amp, fade in partials:
        a = amp
        for i in range(total):
            out[i] += a * math.sin(step * i)
            a *= fade

    attack = int(0.003 * SAMPLE_RATE)       # 3 ms ramp-in avoids a click
    for i in range(attack):
        out[i] *= i / attack
    tail = int(0.06 * SAMPLE_RATE)          # 60 ms fade-out at the end
    for i in range(tail):
        out[-tail + i] *= 1 - i / tail
    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.8 for s in out]


def write_wav(path: str, samples: list[float]) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * 32767)) for s in samples))


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for midi in range(LOWEST, HIGHEST + 1):
        write_wav(os.path.join(OUT_DIR, f"n{midi}.wav"), pluck(midi))
    print(f"Wrote {HIGHEST - LOWEST + 1} files to {os.path.abspath(OUT_DIR)}")
