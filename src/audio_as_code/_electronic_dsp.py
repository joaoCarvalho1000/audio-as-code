"""Band-limited building blocks for designed electronic voices, not circuit replicas."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .acoustics import nyquist_gain

Signal = NDArray[np.float64]


def oscillator_phase(
    t: Signal, frequency: float, glide: float = 0, glide_seconds: float = 0.08
) -> tuple[Signal, Signal]:
    """Integrate an exponential frequency glide exactly; offset is in semitones."""
    offset = np.expm1(glide * np.log(2) / 12)
    instantaneous = frequency * (1 + offset * np.exp(-t / glide_seconds))
    phase = 2 * np.pi * frequency * (t - offset * glide_seconds * np.expm1(-t / glide_seconds))
    return phase, instantaneous


def harmonic_oscillator(
    phase: Signal,
    frequency: Signal,
    rate: int,
    cutoff: Signal,
    resonance: float = 0,
    *,
    pulse_width: Signal | float | None = None,
    phase_offset: float = 0,
    tilt: float = 1,
) -> Signal:
    """Finite Fourier oscillator with a moving analog low-pass magnitude response.

    Filtering partials independently is a spectral approximation, not a recursive
    filter or a self-oscillating ladder. Harmonic count and Nyquist taper bound
    aliasing; rapid envelopes/modulation are not strictly band-limited.
    """
    result = np.zeros(len(phase))
    if not len(phase):
        return result
    count = min(96, int(rate * 0.49 / max(float(np.min(frequency)), 1)))
    q = 0.5 + 4.5 * resonance
    for harmonic in range(1, count + 1):
        partial_frequency = frequency * harmonic
        ratio = partial_frequency / cutoff
        response = 1 / np.sqrt((1 - ratio * ratio) ** 2 + (ratio / q) ** 2)
        # Modest compensation keeps extreme resonances useful without per-note
        # peak normalization (which would erase intended envelope dynamics).
        response /= 1 + 1.5 * resonance
        coefficient = 1 / harmonic**tilt
        if pulse_width is not None:
            coefficient *= 2 * np.sin(np.pi * harmonic * pulse_width)
            # A centered pulse is even: its Fourier basis is cosine. Sine with
            # these coefficients is the quadrature waveform, not a pulse train.
            partial = np.cos(harmonic * (phase + phase_offset))
        else:
            partial = np.sin(harmonic * (phase + phase_offset))
        result += coefficient * partial * response * nyquist_gain(partial_frequency, rate)
    return result * (0.18 if pulse_width is not None else 0.36)


def decimate(signal: Signal, factor: int = 4) -> Signal:
    """Windowed-sinc low-pass before decimation, with centered delay compensation.

    Zero padding prevents circular wraparound. Fixed support makes the filter's
    memory bounded and deterministic. The caller generates at factor * rate.
    """
    taps = np.arange(-32 * factor, 32 * factor + 1)
    kernel = np.sinc(taps * 0.9 / factor) * np.kaiser(len(taps), 8.6)
    kernel /= np.sum(kernel)
    pad = len(kernel) // 2
    return np.convolve(np.pad(signal, (pad, pad)), kernel, mode="valid")[::factor]


def interpolate(signal: Signal, factor: int = 4) -> Signal:
    """Reconstruct with a windowed sinc before a nonlinear processing stage.

    Linear interpolation leaves imaging energy that a following waveshaper can
    fold into the audible band. This FIR suppresses those images first; its
    centered delay is compensated, with silence outside the supplied signal.
    """
    if not len(signal):
        return np.zeros(0)
    taps = np.arange(-32 * factor, 32 * factor + 1)
    kernel = np.sinc(taps / factor) * np.kaiser(len(taps), 8.6)
    kernel *= factor / np.sum(kernel)
    expanded = np.zeros(len(signal) * factor)
    expanded[::factor] = signal
    pad = len(kernel) // 2
    return np.convolve(np.pad(expanded, (pad, pad)), kernel, mode="valid")


def fm_tone(
    t: Signal,
    frequency: float,
    rate: int,
    index: Signal,
    ratio: float,
    glide: float = 0,
    glide_seconds: float = 0.08,
) -> Signal:
    """Four-times-oversampled two-operator phase modulation with a bandwidth guard."""
    if not len(t):
        return np.zeros(0)
    oversampled_t = np.arange(len(t) * 4) / (rate * 4)
    phase, instantaneous = oscillator_phase(oversampled_t, frequency, glide, glide_seconds)
    modulation = np.interp(oversampled_t, t, index)
    # Smoothly reduce the modulation index in very high registers. This guard
    # leaves substantial oversampling headroom for the FM sideband series.
    budget = np.maximum(0, (rate * 1.7 / instantaneous - 1) / ratio - 2)
    modulation = np.minimum(modulation, budget)
    carrier = np.sin(phase + modulation * np.sin(ratio * phase))
    carrier *= nyquist_gain(instantaneous, rate)
    return decimate(carrier)
