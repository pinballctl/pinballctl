#!/usr/bin/env python3
"""Reproduce original synthesized backglass cues; no sampled or game audio."""
import math
from pathlib import Path
import struct
import wave

RATE = 22050
OUT = Path(__file__).resolve().parents[1] / 'zelda' / 'assets'


def write(name, duration, notes):
    samples = []
    for i in range(round(duration * RATE)):
        t = i / RATE
        value = 0.0
        for start, length, frequency, amplitude in notes:
            local = t - start
            if 0 <= local < length:
                envelope = min(1.0, local / 0.025) * min(1.0, (length - local) / 0.15)
                envelope *= math.exp(-local * (1.4 if name not in ('ambient', 'attract') else 0.1))
                value += amplitude * envelope * (math.sin(math.tau * frequency * local) + 0.18 * math.sin(math.tau * frequency * 2 * local))
        samples.append(struct.pack('<h', round(max(-0.95, min(0.95, value)) * 32767)))
    with wave.open(str(OUT / f'{name}.wav'), 'wb') as audio:
        audio.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        audio.writeframes(b''.join(samples))


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    write('move', 0.25, [(0, 0.22, 659.25, 0.18)])
    write('confirm', 0.8, [(0, 0.45, 392, 0.18), (0.12, 0.6, 587.33, 0.16)])
    write('award', 2.8, [(i * 0.18, 1.7, f, 0.15) for i, f in enumerate([293.66, 440, 587.33, 739.99, 880])])
    write('dark', 2.4, [(0, 2.4, 73.42, 0.2), (0.1, 2.2, 110, 0.15), (0.2, 2, 155.56, 0.1)])
    write('ambient', 12, [(0, 12, f, 0.1) for f in [146.83, 220, 293.66]] + [(3, 6, 440, 0.03), (6, 5, 587.33, 0.03)])

    # Original 44-second opening-film score, aligned to the seven edits.
    # Open fifths -> rising tension -> bright resolution; no borrowed melody.
    score = []
    for start, length, chord in [
        (0, 7, [146.83, 220, 293.66]), (7, 6, [174.61, 261.63, 349.23]),
        (13, 7, [196, 293.66, 392]), (20, 6, [110, 155.56, 220]),
        (26, 5, [146.83, 220, 369.99]), (31, 8, [196, 293.66, 392]),
        (39, 5, [146.83, 220, 293.66]),
    ]:
        score.extend((start, length, frequency, 0.12) for frequency in chord)
    for index, frequency in enumerate([587.33, 440, 659.25, 493.88, 783.99, 659.25]):
        score.append((13 + index * 0.9, 1.5, frequency, 0.07))
    for index, frequency in enumerate([392, 493.88, 587.33, 783.99, 587.33, 880]):
        score.append((31 + index * 0.75, 2.0, frequency, 0.10))
    write('attract', 44, score)
