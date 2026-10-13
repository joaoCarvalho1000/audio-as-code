"""Bounded, score-local procedural patches. No assets, callbacks or global registry."""

from __future__ import annotations

import hashlib

import numpy as np

from ._electronic_dsp import fm_tone
from .acoustics import nyquist_gain
from .model import CustomInstrument, Envelope, Filter, FMLayer, ModalLayer, NoiseLayer


def _envelope(env: Envelope, frames: int, held: int, rate: int, release: float) -> np.ndarray:
    t = np.arange(frames) / rate
    attack = env.attack_seconds
    curve = np.where(
        t < attack,
        t / attack,
        1 - (1 - env.sustain) * np.minimum(1, (t - attack) / env.decay_seconds),
    )
    if held < frames:
        count = min(frames - held, round(release * rate))
        level = curve[max(0, held - 1)]
        curve[held:] = 0
        if count:
            curve[held : held + count] = level * np.linspace(1, 0, count)
    else:
        # Explicit zero release still ends cleanly inside the written gate.
        count = min(frames, max(2, round(0.002 * rate)))
        curve[-count:] *= np.linspace(1, 0, count)
    return curve


def synthesize(
    patch: CustomInstrument,
    frequency: float,
    frames: int,
    held_frames: int,
    rate: int,
    seed: int,
    release_override: float | None = None,
) -> np.ndarray:
    """Render mono float32; the ordinary renderer applies velocity, gain and effects."""
    t = np.arange(frames, dtype=np.float64) / rate
    result = np.zeros(frames)
    for index, layer in enumerate(patch.layers):
        layer_seed = int.from_bytes(
            hashlib.sha256(f"{seed}:layer:{index}".encode()).digest()[:8], "little"
        )
        rng = np.random.default_rng(layer_seed)
        signal = np.zeros(frames)
        if isinstance(layer, NoiseLayer):
            signal = rng.uniform(-1, 1, frames)
        else:
            f = frequency * 2 ** (layer.tuning_semitones / 12)
            phase = 2 * np.pi * f * t
            if isinstance(layer, ModalLayer):
                for partial in layer.partials:
                    pf = f * partial.ratio
                    if pf < rate * 0.49:
                        signal += (
                            partial.amplitude
                            * nyquist_gain(pf, rate)
                            * np.sin(phase * partial.ratio)
                            * np.exp(-t / partial.decay_seconds)
                        )
            elif isinstance(layer, FMLayer):
                if f < rate * 0.49:
                    signal = fm_tone(
                        t,
                        f,
                        rate,
                        layer.index * np.exp(-t / layer.index_decay_seconds),
                        layer.ratio,
                    ) * nyquist_gain(f, rate)
            else:
                # Fixed coefficients: removing inaudible partials never boosts the rest.
                count = min(96, int(rate * 0.49 / f))
                offset = rng.uniform(0, 2 * np.pi)
                for harmonic in range(1, count + 1):
                    if layer.waveform == "sine":
                        amplitude = 1.0 if harmonic == 1 else 0.0
                    elif layer.waveform == "triangle":
                        amplitude = (
                            8 / np.pi**2 * (-1) ** ((harmonic - 1) // 2) / harmonic**2
                            if harmonic % 2
                            else 0.0
                        )
                    elif layer.waveform == "saw":
                        amplitude = 2 / (np.pi * harmonic)
                    else:
                        amplitude = (
                            4 * np.sin(np.pi * harmonic * layer.pulse_width) / (np.pi * harmonic)
                        )
                    angle = harmonic * (phase + offset)
                    wave = np.cos(angle) if layer.waveform == "pulse" else np.sin(angle)
                    signal += amplitude * wave * nyquist_gain(f * harmonic, rate)
        release = layer.envelope.release_seconds if release_override is None else release_override
        result += (
            layer.gain * signal * _envelope(layer.envelope, frames, held_frames, rate, release)
        )
    if patch.filter is not None:
        from ._modulation_effects import _filter

        stereo = np.column_stack((result, result))
        result = _filter(stereo, rate, Filter(**patch.filter.model_dump()))[:, 0]
        # Patch filters are contained in the note envelope, without an extra tail.
        count = min(frames, max(2, round(0.002 * rate)))
        result[-count:] *= np.linspace(1, 0, count)
    result[0] = result[-1] = 0
    return result.astype(np.float32)
