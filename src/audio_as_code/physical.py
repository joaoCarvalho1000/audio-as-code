"""Sample-free physical/modal approximations, implemented with NumPy only.

The string uses a passive Karplus-Strong feedback loop with phase-compensated
fractional delay. Bar and bell presets sum the impulse responses of damped modes.
All excitations are generated here; no recordings or measured impulse responses.
See docs/synthesis.md for equations, scope, and references.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from .acoustics import colored_noise, nyquist_gain, resonant_body, struck_mode
from .instruments import require_instrument
from .model import Tone


@dataclass(frozen=True)
class ModalProfile:
    ratios: tuple[float, ...]
    amplitudes: tuple[float, ...]
    lifetimes: tuple[float, ...]


_MODAL_PROFILES = MappingProxyType(
    {
        # Approximate tuned wooden bar; higher modes die away much sooner.
        "marimba": ModalProfile((1, 4, 10, 17), (1, 0.32, 0.12, 0.04), (1, 0.32, 0.14, 0.08)),
        # Designed inharmonic chime, not a model fitted to a particular bell.
        "bell": ModalProfile(
            (1, 2, 2.756, 4.07, 5.404, 6.81),
            (1, 0.38, 0.32, 0.22, 0.12, 0.08),
            (1, 0.8, 0.65, 0.5, 0.4, 0.3),
        ),
    }
)


def _string(
    frequency: float,
    frames: int,
    rate: int,
    seed: int,
    brightness: float,
    decay: float,
    position: float,
) -> NDArray[np.float64]:
    omega = 2 * math.pi * frequency / rate
    # A passive one-zero filter dissipates high frequencies on every round trip.
    damping = 0.3 - brightness * 0.25
    damping_response = (1 - damping) + damping * np.exp(-1j * omega)
    damping_phase = -float(np.angle(damping_response))
    delay = max(1, math.floor((2 * math.pi - damping_phase) / omega))
    residual = max(0.0, 2 * math.pi - damping_phase - delay * omega)
    # Solve the linear interpolator's phase at the fundamental, rather than
    # assuming its group delay equals its interpolation weight at every pitch.
    fractional = math.sin(residual) / (math.sin(omega - residual) + math.sin(residual))
    fractional = min(1.0, max(0.0, fractional))
    interpolation_response = (1 - fractional) + fractional * np.exp(-1j * omega)
    target_loss = math.exp(-math.log(1000) / (frequency * decay))
    filter_loss = abs(damping_response * interpolation_response)
    loop_gain = min(0.9999, target_loss / max(filter_loss, 1e-12))
    coefficients = loop_gain * np.array(
        [
            (1 - damping) * (1 - fractional),
            damping * (1 - fractional) + (1 - damping) * fractional,
            damping * fractional,
        ]
    )

    rng = np.random.Generator(np.random.PCG64(seed))
    excitation = rng.uniform(-1, 1, delay)
    excitation -= np.roll(excitation, max(1, round(position * delay)))
    # Shape a code-generated pluck, emphasizing low string modes while retaining
    # the noise burst's transient. This spectrum is generated afresh per note.
    harmonics = np.arange(delay // 2 + 1)
    spectrum = np.fft.rfft(excitation)
    spectrum *= 1 / (1 + (harmonics / (5 + brightness * 24)) ** 2)
    excitation = np.fft.irfft(spectrum, n=delay)
    location = np.arange(delay) / delay
    displacement = np.where(
        location <= position, location / position, (1 - location) / (1 - position)
    )
    excitation = 0.65 * excitation + 0.55 * (displacement - np.mean(displacement))
    excitation += 0.3 * np.sin(2 * np.pi * location)
    excitation -= np.mean(excitation)
    peak = float(np.max(np.abs(excitation)))
    if peak:
        excitation *= 0.8 / peak

    padding = delay + 2
    history = np.zeros(frames + padding)
    initial = min(delay, frames)
    history[padding : padding + initial] = excitation[:initial]
    # A block never exceeds the shortest delay, so every feedback read refers
    # to an already-computed block. No Python loop per individual audio sample.
    for start in range(padding, len(history), delay):
        stop = min(len(history), start + delay)
        history[start:stop] += (
            coefficients[0] * history[start - delay : stop - delay]
            + coefficients[1] * history[start - delay - 1 : stop - delay - 1]
            + coefficients[2] * history[start - delay - 2 : stop - delay - 2]
        )
    signal = history[padding:]
    # Body modes are driven by the vibrating string, not an independent knock.
    t = np.arange(frames) / rate
    signal += (
        0.009 * brightness * colored_noise(frames, rate, seed + 1, 1600, 8000) * np.exp(-t / 0.006)
    )
    return resonant_body(
        signal, rate, ((110, 0.19, 0.45), (205, 0.12, 0.35), (430, 0.075, 0.2)), wet=0.22
    )


def _modes(
    instrument: str,
    frequency: float,
    frames: int,
    rate: int,
    brightness: float,
    decay: float,
) -> NDArray[np.float64]:
    t = np.arange(frames, dtype=np.float64) / rate
    profile = _MODAL_PROFILES[instrument]
    signal = np.zeros(frames)
    total_weight = 0.0
    for index, (ratio, amplitude, lifetime) in enumerate(
        zip(profile.ratios, profile.amplitudes, profile.lifetimes, strict=True)
    ):
        amplitude *= 1 if index == 0 else 0.15 + brightness * 1.7
        total_weight += amplitude
        if frequency * ratio >= rate * 0.49:
            continue
        if instrument == "marimba":
            contact = min(0.65 / frequency, 0.0035 * (1.2 - 0.8 * brightness))
            response = struck_mode(
                t, frequency * ratio, math.log(1000) / (decay * lifetime), contact
            )
        else:
            contact = min(0.45 / frequency, 0.0014 * (1.25 - 0.8 * brightness))
            damping = math.log(1000) / (decay * lifetime)
            partial = struck_mode(t, frequency * ratio, damping, contact)
            split = frequency * ratio * (1 + 0.0006 * (index + 1))
            response = 0.8 * partial + 0.2 * struck_mode(t, split, damping, contact) * nyquist_gain(
                split, rate
            )
        signal += amplitude * response * nyquist_gain(frequency * ratio, rate)
    return signal * (0.9 / total_weight) if total_weight else signal


def synthesize(
    instrument: str,
    frequency: float,
    frames: int,
    rate: int,
    seed: int,
    velocity: float,
    tone: Tone | None,
) -> NDArray[np.float64]:
    instrument_info = require_instrument(instrument)
    if instrument not in {"guitar", "marimba", "bell"}:
        raise ValueError(f"{instrument!r} does not use the original physical/modal engine")
    settings = tone or Tone()
    if frequency >= rate / 2:
        return np.zeros(frames)
    brightness = min(1.0, settings.brightness * 0.75 + velocity * 0.25)
    decay = (
        settings.decay_seconds
        if settings.decay_seconds is not None
        else instrument_info.default_decay_seconds
    )
    if decay is None:
        raise ValueError(f"{instrument!r} has no default decay configured")
    if instrument_info.engine == "string":
        return _string(
            frequency,
            frames,
            rate,
            seed,
            brightness,
            decay,
            settings.pluck_position if settings.pluck_position is not None else 0.22,
        )
    return _modes(instrument, frequency, frames, rate, brightness, decay)
