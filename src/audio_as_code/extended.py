"""Paired strings, cantilever lamellae, struck bars and a recorder jet spectrum.

All excitations and resonator responses are generated from equations. Parameters
are designed rather than fitted to recordings. See docs/extended-instruments.md
for the physical motivation and the deliberately limited model boundaries.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from .acoustics import (
    colored_noise,
    modulate_noise,
    nyquist_gain,
    resonant_body,
    slow_variation,
    struck_mode,
)
from .instruments import require_instrument
from .model import Tone

Signal = NDArray[np.float64]
EXTENDED_INSTRUMENTS = frozenset({"mandolin", "kalimba", "celesta", "recorder"})


def _mandolin(
    frequency: float,
    t: Signal,
    rate: int,
    seed: int,
    brightness: float,
    decay: float,
    position: float,
    detune: float,
) -> Signal:
    """Two-string modal pairs with shared bridge stiffness and radiation loss.

    The symmetric stiffness matrix gives stable real normal modes. Damping is
    projected onto each mode; off-diagonal dissipative coupling is neglected.
    detune is the TOTAL uncoupled-string separation in cents, not +/- detune.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    signal = np.zeros(len(t))
    excitation = np.array([1.0, rng.uniform(0.88, 0.96)])
    radiation = np.array([1.0, 1.0])
    total = 0.0
    stiffness = 0.000018 * (1 + frequency / 600)
    for harmonic in range(1, 33):
        center = frequency * harmonic * math.sqrt((1 + stiffness * harmonic**2) / (1 + stiffness))
        uncoupled = np.array([2 ** (-detune / 2400), 2 ** (detune / 2400)])
        # A small common-bridge restoring term separates bright and dark modes.
        coupling = 0.00035 / (1 + harmonic * 0.08)
        eigenvalues, vectors = np.linalg.eigh(np.diag(uncoupled**2) + coupling * np.ones((2, 2)))
        ratios = np.sqrt(eigenvalues)
        # Preserve the written pitch as the geometric center of the mode pair.
        ratios /= math.sqrt(ratios[0] * ratios[1])
        pluck = math.sin(math.pi * harmonic * position) / harmonic**1.2
        pluck *= math.exp(-(harmonic - 1) / (3.0 + 15 * brightness))
        pluck *= rng.uniform(0.98, 1.02)
        for index, ratio in enumerate(ratios):
            mode = vectors[:, index]
            bridge = float(mode @ radiation)
            amplitude = pluck * float(mode @ excitation) * bridge
            total += abs(amplitude)
            f = center * ratio
            if f >= rate * 0.49:
                continue
            loss = (0.45 + 0.42 * bridge**2) * (1 + 0.12 * (harmonic - 1) ** 1.2)
            signal += (
                amplitude
                * np.sin(2 * np.pi * f * t)
                * np.exp(-math.log(1000) * loss * t / decay)
                * nyquist_gain(f, rate)
            )
    if total:
        signal *= 0.86 / total
    # A very short generated pick scrape drives the same body as the strings.
    signal += (
        0.018 * brightness * colored_noise(len(t), rate, seed + 1, 1700, 8000) * np.exp(-t / 0.005)
    )
    return resonant_body(
        signal,
        rate,
        ((310, 0.11, 0.45), (650, 0.075, 0.35), (1550, 0.045, 0.2)),
        wet=0.18,
    )


def _kalimba(
    frequency: float,
    t: Signal,
    rate: int,
    seed: int,
    brightness: float,
    decay: float,
) -> Signal:
    """Finite thumb-contact forcing of fixed-free lamella modes and a wooden box."""
    # Squared roots of cos(beta)*cosh(beta)=-1, relative to the first root.
    roots = (1.87510407, 4.69409113, 7.85475744, 10.99554073)
    amplitudes = (1.0, 0.26, 0.095, 0.035)
    lifetimes = (1.0, 0.22, 0.085, 0.04)
    contact = min(0.42 / frequency, 0.00055 * (1.3 - 0.9 * brightness))
    rng = np.random.Generator(np.random.PCG64(seed))
    signal = np.zeros(len(t))
    total = 0.0
    for index, (root, amplitude, lifetime) in enumerate(
        zip(roots, amplitudes, lifetimes, strict=True)
    ):
        f = frequency * (root / roots[0]) ** 2
        amplitude *= (1 if index == 0 else 0.3 + 1.4 * brightness) * rng.uniform(0.98, 1.02)
        total += amplitude
        if f < rate * 0.49:
            signal += (
                amplitude
                * struck_mode(
                    t,
                    f,
                    math.log(1000) / (decay * lifetime),
                    contact,
                )
                * nyquist_gain(f, rate)
            )
    signal *= 0.86 / total
    # A thumb/metal contact transient, not a sampled click or a buzz attachment.
    signal += (
        0.012 * brightness * colored_noise(len(t), rate, seed + 1, 900, 6500) * np.exp(-t / 0.003)
    )
    return resonant_body(
        signal,
        rate,
        ((185, 0.18, 0.45), (430, 0.10, 0.35), (1100, 0.045, 0.2)),
        wet=0.22,
    )


def _celesta(
    frequency: float,
    t: Signal,
    rate: int,
    seed: int,
    brightness: float,
    decay: float,
) -> Signal:
    """Felt-hammer forcing of free-free metal-bar modes and a pitch-matched box."""
    # First four non-rigid roots of cos(beta)*cosh(beta)=1.
    roots = (4.73004074, 7.85320462, 10.99560784, 14.13716549)
    amplitudes = (1.0, 0.48, 0.23, 0.11)
    lifetimes = (1.0, 0.62, 0.30, 0.16)
    contact = min(0.55 / frequency, 0.0034 * (1.2 - 0.85 * brightness))
    rng = np.random.Generator(np.random.PCG64(seed))
    signal = np.zeros(len(t))
    total = 0.0
    for index, (root, amplitude, lifetime) in enumerate(
        zip(roots, amplitudes, lifetimes, strict=True)
    ):
        f = frequency * (root / roots[0]) ** 2
        amplitude *= (1 if index == 0 else 0.35 + 1.3 * brightness) * rng.uniform(0.985, 1.015)
        total += amplitude
        if f < rate * 0.49:
            signal += (
                amplitude
                * struck_mode(
                    t,
                    f,
                    math.log(1000) / (decay * lifetime),
                    contact,
                )
                * nyquist_gain(f, rate)
            )
    signal *= 0.9 / total
    # The resonator is driven by bar motion. It is an analytic one-way response,
    # not an independent ringing oscillator or measured instrument response.
    return resonant_body(
        signal,
        rate,
        ((frequency, 0.22, 1.0), (frequency * 2.02, 0.085, 0.16)),
        wet=0.24,
    )


def _recorder(
    frequency: float,
    t: Signal,
    rate: int,
    seed: int,
    brightness: float,
    settings: dict,
) -> Signal:
    """Band-limited jet-source harmonics with an idealized bore/radiation filter.

    The jet waveform is Fourier-analyzed on a phase grid, then reconstructed
    only with audible partials. No nonlinear audio-rate waveshaper can alias.
    This is a prescribed source/filter model, not a self-oscillating jet solver.
    """
    depth = settings["vibrato_depth_cents"]
    vibrato_rate = settings["vibrato_rate_hz"]
    motion = slow_variation(t, seed, 0.6)
    vibrato = (
        depth * (1 - np.exp(-np.maximum(t - 0.08, 0) / 0.22)) * np.sin(2 * np.pi * vibrato_rate * t)
    )
    settling = -2.0 * np.exp(-t / 0.018)
    frequencies = frequency * 2 ** ((vibrato + settling + 0.35 * motion) / 1200)
    phase = np.zeros(len(t))
    phase[1:] = 2 * np.pi * np.cumsum((frequencies[:-1] + frequencies[1:]) * 0.5) / rate
    theta = 2 * np.pi * np.arange(2048) / 2048
    drive = 0.85 + 1.6 * brightness
    offset = 0.10 + 0.18 * brightness
    jet = np.tanh(drive * (np.sin(theta) + offset))
    coefficients = np.fft.rfft(jet) / len(theta)
    signal = np.zeros(len(t))
    total = 0.0
    pressure = 1 + 0.018 * motion
    # The pitch-scaled bore roll-off and fixed radiation shelf are designed
    # envelopes, without fingering-dependent impedances or measured formants.
    cutoff = 3.0 + 5.0 * brightness
    for harmonic in range(1, 21):
        coefficient = 2 * coefficients[harmonic]
        transfer = harmonic**0.35 / math.sqrt(1 + (harmonic / cutoff) ** 4)
        transfer /= math.sqrt(1 + (frequency * harmonic / 8500) ** 2)
        amplitude = abs(coefficient) * transfer
        total += amplitude
        if float(np.min(frequencies)) * harmonic >= rate * 0.49:
            continue
        onset = 1 - np.exp(-t / (0.012 + harmonic * 0.0015))
        signal += (
            amplitude
            * onset
            * pressure
            * np.cos(harmonic * phase + np.angle(coefficient))
            * nyquist_gain(frequencies * harmonic, rate)
        )
    if total:
        signal *= 0.79 / total
    breath = settings["breath"]
    if breath:
        noise = colored_noise(len(t), rate, seed + 1, 1200, 7500)
        maximum_frequency = frequency * 2 ** ((depth + 0.35) / 1200) + 2
        noise = modulate_noise(noise, phase, maximum_frequency, rate, 0.18)
        envelope = (1 - np.exp(-t / 0.003)) * (0.55 + 0.8 * np.exp(-t / 0.045))
        signal += 0.15 * breath * noise * envelope * pressure
    return signal


def synthesize(
    instrument: str,
    frequency: float,
    frames: int,
    rate: int,
    seed: int,
    velocity: float,
    tone: Tone | None,
) -> Signal:
    """Return generated float64 mono; the renderer applies note gates and gain."""
    if instrument not in EXTENDED_INSTRUMENTS:
        raise ValueError(f"No extended model for {instrument!r}")
    info = require_instrument(instrument)
    if frames < 1 or frequency >= rate / 2:
        return np.zeros(frames, dtype=np.float64)
    tone = tone or Tone()
    settings = dict(info.default_tone)
    settings.update({key: value for key, value in tone.model_dump().items() if value is not None})
    brightness = min(1.0, settings["brightness"] * 0.75 + velocity * 0.25)
    decay = settings.get("decay_seconds", info.default_decay_seconds)
    t = np.arange(frames, dtype=np.float64) / rate
    if instrument == "mandolin":
        return _mandolin(
            frequency,
            t,
            rate,
            seed,
            brightness,
            decay,
            settings["pluck_position"],
            settings["detune_cents"],
        )
    if instrument == "kalimba":
        return _kalimba(frequency, t, rate, seed, brightness, decay)
    if instrument == "celesta":
        return _celesta(frequency, t, rate, seed, brightness, decay)
    return _recorder(frequency, t, rate, seed, brightness, settings)
