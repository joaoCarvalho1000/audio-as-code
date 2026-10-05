"""Original oscillator/noise percussion; no recorded hits or circuit emulation."""

from __future__ import annotations

import numpy as np

from ._electronic_dsp import Signal, fm_tone
from .acoustics import colored_noise, nyquist_gain

DRUM_VOICES = frozenset(
    {
        "kick_808",
        "kick_909",
        "clap",
        "electronic_snare",
        "metal_hat",
        "open_hat",
        "electronic_ride",
        "fm_percussion",
    }
)


def percussion(
    instrument: str, t: Signal, rate: int, seed: int, velocity: float, settings: dict
) -> Signal:
    brightness = settings["brightness"]
    decay = settings["decay_seconds"]
    tuning = 2 ** (settings.get("tuning_semitones", 0) / 12)
    noise = colored_noise(len(t), rate, seed, 1200 + brightness * 3000, rate * 0.43)
    if instrument in {"kick_808", "kick_909"}:
        punch = instrument == "kick_909"
        base = (52 if punch else 45) * tuning
        sweep = (90 if punch else 58) * tuning * (0.6 + velocity * 0.5)
        tau = 0.018 if punch else 0.035
        phase = 2 * np.pi * (base * t - sweep * tau * np.expm1(-t / tau))
        signal = np.sin(phase) * np.exp(-6.9 * t / decay)
        signal += (0.12 if punch else 0.025) * noise * np.exp(-t / 0.009)
        if punch:
            signal += 0.17 * np.sin(phase * 2) * np.exp(-t / 0.025)
        return 0.8 * signal
    if instrument == "clap":
        # Three distinct palms/collisions, followed by a diffuse generated tail.
        burst = np.zeros(len(t))
        for onset in (0, 0.009, 0.019):
            age = np.maximum(t - onset, 0)
            burst += (t >= onset) * (1 - np.exp(-age / 0.0008)) * np.exp(-age / 0.004)
        age = np.maximum(t - 0.027, 0)
        burst += (t >= 0.027) * (1 - np.exp(-age / 0.002)) * np.exp(-6.9 * age / decay)
        return noise * burst * 2.0
    if instrument == "electronic_snare":
        body = sum(
            weight
            * np.sin(2 * np.pi * f * tuning * t)
            * nyquist_gain(f * tuning, rate)
            * np.exp(-6.9 * t / (decay * lifetime))
            for f, weight, lifetime in ((185, 0.55, 0.8), (330, 0.28, 0.45), (460, 0.1, 0.25))
        )
        snap = noise * (1 + 0.25 * np.sin(2 * np.pi * 95 * t))
        return body + (0.9 + brightness) * snap * np.exp(-6.9 * t / decay)
    if instrument == "fm_percussion":
        index = settings.get("fm_index", 3) * (0.4 + 1.2 * brightness) * np.exp(-4 * t / decay)
        tone = fm_tone(t, 220 * tuning, rate, index, settings.get("fm_ratio", 3.41))
        return 0.6 * tone * np.exp(-6.9 * t / decay)
    # Six inharmonic oscillator ladders approximate a metallic electronic source.
    metal = np.zeros(len(t))
    for f in (317, 465, 631, 857, 1123, 1471):
        for harmonic in (1, 3, 5, 7, 9, 11, 13):
            hz = f * harmonic * tuning
            if hz >= rate * 0.49:
                continue
            highpass = hz**2 / (hz**2 + (2200 + brightness * 2200) ** 2)
            # Upper bands lose energy sooner; the longer open-hat/ride settings
            # reveal a darker ring instead of scaling one frozen spectrum.
            loss = 0.72 + 0.45 * (hz / 4000) ** 0.7
            envelope = np.exp(-6.9 * t * loss / decay)
            metal += (
                np.sin(2 * np.pi * hz * t) * highpass * nyquist_gain(hz, rate) * envelope / harmonic
            )
    metal *= 0.14
    if instrument == "electronic_ride":
        bell = sum(
            0.08
            * np.sin(2 * np.pi * f * tuning * t)
            * nyquist_gain(f * tuning, rate)
            * np.exp(-6.9 * t * (0.65 + 0.2 * f / 4000) / decay)
            for f in (2423, 3871, 5669)
        )
        metal += bell
    return metal + 0.45 * noise * np.exp(-6.9 * t / (decay * 0.65))
