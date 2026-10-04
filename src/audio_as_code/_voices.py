"""Instrument dispatch and note envelopes; scheduling and mixing live in render."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ._audio import Audio
from .acoustics import colored_noise, nyquist_gain
from .extended import EXTENDED_INSTRUMENTS
from .extended import synthesize as synthesize_extended
from .instruments import KIT_NOTES, PHYSICAL_INSTRUMENTS, get_instrument
from .model import Tone
from .orchestra import EXTRA_INSTRUMENTS
from .orchestra import synthesize as synthesize_orchestra
from .physical import synthesize

_HARMONICS = {
    "sine": [(1, 1)],
    "triangle": [(n, (-1) ** ((n - 1) // 2) / n**2) for n in range(1, 16, 2)],
    "pluck": [(n, 1 / n**1.6) for n in range(1, 9)],
    "bass": [(1, 1), (2, 0.35), (3, 0.12)],
    "pad": [(1, 1), (2, 0.25), (3, 0.12), (4, 0.06)],
}

_ATTACK_SECONDS = {
    "pad": 0.08,
    "guitar": 0.001,
    "marimba": 0.0005,
    "piano": 0.0005,
    "xylophone": 0.0005,
    "glockenspiel": 0.0005,
    "mandolin": 0.001,
    "kalimba": 0.0005,
    "celesta": 0.0005,
    "recorder": 0.003,
}

_RELEASE_SECONDS = {
    "pad": 0.15,
    "guitar": 0.065,
    "electric_guitar": 0.055,
    "bass_guitar": 0.07,
    "harp": 0.12,
    "ukulele": 0.045,
    "banjo": 0.035,
    "harpsichord": 0.04,
    "piano": 0.12,
    "electric_piano": 0.09,
    "marimba": 0.055,
    "bell": 0.12,
    "xylophone": 0.035,
    "vibraphone": 0.12,
    "glockenspiel": 0.1,
    "violin": 0.09,
    "viola": 0.11,
    "cello": 0.13,
    "double_bass": 0.16,
    "flute": 0.08,
    "clarinet": 0.055,
    "saxophone": 0.075,
    "oboe": 0.065,
    "bassoon": 0.08,
    "trumpet": 0.055,
    "trombone": 0.075,
    "french_horn": 0.1,
    "tuba": 0.13,
    "organ": 0.06,
    "theremin": 0.1,
    "timpani": 0.12,
    "cymbal": 0.1,
    "tambourine": 0.045,
    "mandolin": 0.06,
    "kalimba": 0.08,
    "celesta": 0.1,
    "recorder": 0.055,
}


def _electronic_voice(
    instrument: str, frequency: float, frames: int, rate: int, seed: int, velocity: float
) -> NDArray[np.float64]:
    """Generate the original harmonic voices and electronic drum sounds."""
    t = np.arange(frames, dtype=np.float64) / rate
    if instrument == "kick":
        # Analytic integral of an exponential pitch sweep; independent of sample rate.
        sweep = 60 + 60 * velocity
        phase = 2 * np.pi * (48 * t + sweep * (1 - np.exp(-35 * t)) / 35)
        signal = np.sin(phase) * np.exp(-9 * t)
        signal += (
            0.035 * velocity * colored_noise(frames, rate, seed, 1800, 9000) * np.exp(-t / 0.006)
        )
    elif instrument in {"snare", "hat"}:
        if instrument == "snare":
            noise = colored_noise(frames, rate, seed, 1100, 9500)
            body = 0.32 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.045) + 0.14 * np.sin(
                2 * np.pi * 330 * t
            ) * np.exp(-t / 0.028)
            rattle = (
                0.72
                * noise
                * (1 + 0.18 * np.sin(2 * np.pi * 83 * t))
                * np.exp(-t / (0.055 + 0.025 * velocity))
            )
            signal = body + rattle
        else:
            noise = colored_noise(frames, rate, seed, 4500, 16000)
            metal = (
                sum(
                    np.sin(2 * np.pi * f * t) * nyquist_gain(f, rate)
                    for f in (3170, 4211, 5783, 7139, 9323)
                )
                / 5
            )
            signal = (0.65 * noise + 0.12 * metal) * np.exp(-t / (0.018 + 0.01 * velocity))
    else:
        # Finite harmonic sums avoid the unbounded harmonics of naive square/saw waves.
        phase = 2 * np.pi * frequency * t
        harmonics = _HARMONICS[instrument]
        signal = np.zeros(frames)
        weight = 0.0
        for harmonic, amplitude in harmonics:
            if frequency * harmonic >= rate / 2:
                continue
            partial = np.sin(phase * harmonic) * amplitude
            if instrument == "pluck":
                partial *= np.exp(-t * (2.5 + harmonic * 0.8))
            signal += partial
            weight += abs(amplitude)
        if weight:
            signal /= weight
        if instrument == "bass":
            signal *= 0.65 + 0.35 * np.exp(-6 * t)
    return signal


def _voice(
    instrument: str,
    pitch: int,
    frames: int,
    rate: int,
    seed: int,
    velocity: float = 0.8,
    tone: Tone | None = None,
    held_frames: int | None = None,
    articulation: str | None = None,
) -> Audio:
    if articulation is not None and articulation not in get_instrument(instrument).articulations:
        raise ValueError(f"articulation {articulation!r} is not supported by {instrument}")
    if instrument == "drum_machine":
        return _voice(
            KIT_NOTES[pitch], pitch, frames, rate, seed, velocity, held_frames=held_frames
        )
    frequency = 440 * 2 ** ((pitch - 69) / 12)
    if instrument in EXTENDED_INSTRUMENTS:
        signal = synthesize_extended(instrument, frequency, frames, rate, seed, velocity, tone)
    elif instrument in EXTRA_INSTRUMENTS:
        signal = synthesize_orchestra(
            instrument, frequency, frames, rate, seed, velocity, tone, articulation, held_frames
        )
    elif instrument in PHYSICAL_INSTRUMENTS:
        signal = synthesize(instrument, frequency, frames, rate, seed, velocity, tone)
    else:
        signal = _electronic_voice(instrument, frequency, frames, rate, seed, velocity)

    # Every voice begins and ends at zero. Envelope fits even very short notes.
    attack_seconds = _ATTACK_SECONDS.get(instrument, 0.003)
    release_seconds = _RELEASE_SECONDS.get(instrument, 0.02)
    attack = min(max(1, round(attack_seconds * rate)), max(1, (held_frames or frames) // 3))
    release = (
        frames - held_frames
        if held_frames is not None
        else min(max(1, round(release_seconds * rate)), max(1, frames // 3))
    )
    signal[:attack] *= np.linspace(0, 1, attack)
    release_curve = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, release)) if release > 1 else 0
    signal[-release:] *= release_curve
    return signal.astype(np.float32)
