"""Designed dance-music voices using shared harmonic, FM and percussion engines."""

from __future__ import annotations

import numpy as np

from ._electronic_drums import DRUM_VOICES, percussion
from ._electronic_dsp import Signal, fm_tone, harmonic_oscillator, oscillator_phase
from .acoustics import colored_noise, nyquist_gain, struck_mode
from .instruments import require_instrument
from .model import Tone

ELECTRONIC_INSTRUMENTS = DRUM_VOICES | {
    "acid_bass",
    "supersaw",
    "reese_bass",
    "fm_bass",
    "clavinet",
    "string_machine",
    "disco_bass",
    "trance_pluck",
    "fm_bell",
    "wavetable_pad",
    "sync_lead",
    "hoover",
    "sub_bass",
}


def _clavinet(frequency: float, t: Signal, rate: int, settings: dict, seed: int) -> Signal:
    """Finite hammer excitation and dual pickups; no electromechanical feedback."""
    signal = np.zeros(len(t))
    position = settings.get("pluck_position", 0.2)
    decay = settings["decay_seconds"]
    brightness = settings["brightness"]
    contact_seconds = min(0.4 / frequency, 0.0012 * (1.2 - 0.8 * brightness))
    for n in range(1, min(80, int(rate * 0.49 / frequency)) + 1):
        hz = frequency * n
        pickup = np.sin(np.pi * n * 0.18) + 0.55 * np.sin(np.pi * n * 0.31)
        amplitude = np.sin(np.pi * n * position) * pickup / n**0.95
        amplitude *= np.exp(-(n - 1) / (5 + 35 * brightness))
        response = struck_mode(t, hz, 6.9 * (1 + 0.06 * n) / decay, contact_seconds)
        signal += amplitude * response * nyquist_gain(hz, rate)
    contact = colored_noise(len(t), rate, seed, 700, 7000)
    return 0.5 * signal + 0.12 * contact * np.exp(-t / 0.006)


def synthesize(
    instrument: str,
    frequency: float,
    frames: int,
    rate: int,
    seed: int,
    velocity: float,
    tone: Tone | None,
    articulation: str | None = None,
) -> Signal:
    info = require_instrument(instrument)
    if instrument not in ELECTRONIC_INSTRUMENTS:
        raise ValueError(f"No electronic model for {instrument!r}")
    if articulation is not None and articulation not in info.articulations:
        raise ValueError(f"articulation {articulation!r} is not supported by {instrument}")
    if frames < 1:
        return np.zeros(frames)
    settings = dict(info.default_tone)
    settings["decay_seconds"] = info.default_decay_seconds or 1.5
    settings.update({k: v for k, v in (tone or Tone()).model_dump().items() if v is not None})
    settings["brightness"] = 0.75 * settings["brightness"] + 0.25 * velocity
    t = np.arange(frames) / rate
    if instrument in DRUM_VOICES:
        return percussion(instrument, t, rate, seed, velocity, settings)
    if frequency >= rate * 0.49:
        return np.zeros(frames)
    if instrument == "clavinet":
        return _clavinet(frequency, t, rate, settings, seed)
    brightness = settings["brightness"]
    glide = settings.get("glide_semitones", 0)
    glide_time = settings.get("glide_seconds", 0.08)
    phase, instantaneous = oscillator_phase(t, frequency, glide, glide_time)
    decay = settings["decay_seconds"]
    if instrument == "sub_bass":
        return 0.8 * np.sin(phase) * nyquist_gain(instantaneous, rate) + 0.08 * brightness * np.sin(
            2 * phase
        ) * nyquist_gain(2 * instantaneous, rate)
    if instrument in {"fm_bass", "fm_bell"}:
        index = settings.get("fm_index", 3) * (0.3 + 1.4 * brightness)
        if instrument == "fm_bell":
            index = index * np.exp(-4 * t / decay)
        else:
            lfo = settings.get("modulation_rate_hz", 2)
            index = index * (0.55 + 0.45 * np.sin(2 * np.pi * lfo * t) ** 2)
        signal = fm_tone(
            t,
            frequency,
            rate,
            np.broadcast_to(index, t.shape),
            settings.get("fm_ratio", 2),
            glide,
            glide_time,
        )
        if instrument == "fm_bell":
            signal *= np.exp(-6.9 * t / decay)
        else:
            signal = 0.7 * signal + 0.3 * np.sin(phase) * nyquist_gain(instantaneous, rate)
        return 0.65 * signal

    envelope_seconds = settings.get("filter_decay_seconds", 0.25)
    envelope_depth = settings.get("filter_env_octaves", 2)
    accent = 1.4 if articulation == "accented" else 1
    cutoff = settings.get("cutoff_hz", 500 + 6500 * brightness**2)
    cutoff = cutoff * 2 ** (envelope_depth * accent * np.exp(-t / envelope_seconds))
    cutoff = np.clip(cutoff, 30, rate * 0.44)
    resonance = settings.get("resonance", 0.15)
    detune = settings.get("detune_cents", 12)
    rng = np.random.Generator(np.random.PCG64(seed))
    if instrument == "supersaw":
        offsets = (-1, -0.64, -0.28, 0, 0.28, 0.64, 1)
    elif instrument in {"string_machine", "hoover", "wavetable_pad"}:
        offsets = (-1, -0.45, 0, 0.45, 1)
    elif instrument == "reese_bass":
        offsets = (-1, 1)
    else:
        offsets = (0,)
    signal = np.zeros(frames)
    for offset in offsets:
        factor = 2 ** (offset * detune / 1200)
        pulse = None
        if instrument in {"string_machine", "hoover"}:
            pulse = 0.45 + 0.16 * np.sin(2 * np.pi * (0.45 + offset * 0.12) * t)
        elif instrument == "wavetable_pad":
            # Analytic morph of sine-like to saw-like harmonic tables, not recordings.
            pulse = 0.5 + 0.35 * np.sin(2 * np.pi * 0.17 * t)
        phase_offset = rng.uniform(-np.pi, np.pi) if len(offsets) > 1 else 0
        signal += harmonic_oscillator(
            phase * factor,
            instantaneous * factor,
            rate,
            cutoff,
            resonance,
            pulse_width=pulse,
            phase_offset=phase_offset,
            tilt=0.8 + 0.8 * (1 - brightness),
        )
    signal /= np.sqrt(len(offsets))
    if instrument == "sync_lead":
        # A master-periodic Fourier spectrum with a moving formant emulates the
        # audible hard-sync sweep without sampling discontinuous slave resets.
        formant = 2.5 + 3.5 * np.exp(-t / envelope_seconds)
        for n in range(2, min(32, int(rate * 0.49 / frequency)) + 1):
            weight = np.exp(-0.5 * ((n - formant) / 1.2) ** 2) / n
            signal += 0.3 * weight * np.sin(n * phase) * nyquist_gain(n * instantaneous, rate)
    if instrument in {"trance_pluck", "disco_bass"}:
        signal *= np.exp(-6.9 * t / decay)
    elif instrument in {"string_machine", "wavetable_pad"}:
        signal *= 1 - np.exp(-t / (0.055 if instrument == "string_machine" else 0.13))
    elif instrument == "hoover":
        signal += 0.13 * np.sin(phase / 2) * nyquist_gain(instantaneous / 2, rate)
    elif instrument == "reese_bass":
        signal += 0.18 * np.sin(phase) * nyquist_gain(instantaneous, rate)
    return signal * (1 + 0.12 * (accent - 1))
