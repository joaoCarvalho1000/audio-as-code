"""Small deterministic DSP helpers. Every response is calculated from equations."""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from ._fir import convolve_causal, kernel_from_magnitude

Signal = NDArray[np.float64]


def struck_mode(t: Signal, frequency: float, damping: float, contact: float) -> Signal:
    """Damped sine driven by a unit-area, finite raised-cosine force pulse.

    Integrate continuously, then sample: even sub-sample contact times retain
    their area. After contact the mode rings freely at its original frequency.
    Positive unit-area forcing keeps the result bounded by the impulse response.
    This is prescribed one-way forcing, not a nonlinear hammer/contact solver.
    """
    pole = complex(-damping, 2 * np.pi * frequency)
    pulse_frequency = 2 * np.pi / contact
    attacking = t < contact
    u = t[attacking]
    response = np.zeros(len(t), dtype=np.complex128)
    released = 0j
    for weight, offset in ((1, 0), (-0.5, pulse_frequency), (-0.5, -pulse_frequency)):
        denominator = pole - 1j * offset
        # expm1 avoids cancellation for short contacts and low modes. All real
        # exponents are nonpositive, including very short decay settings.
        integral = np.expm1(denominator * u) / denominator
        response[attacking] += weight * np.exp(1j * offset * u) * integral
        released += (
            weight * np.exp(1j * offset * contact) * np.expm1(denominator * contact) / denominator
        )
    response[~attacking] = released * np.exp(pole * (t[~attacking] - contact))
    return response.imag / contact


def nyquist_gain(frequency: Signal | float, rate: int) -> Signal | float:
    """Cosine shoulder leaves room for envelope/modulation sidebands."""
    fraction = np.clip((frequency / rate - 0.45) / 0.04, 0, 1)
    return 0.5 + 0.5 * np.cos(np.pi * fraction)


@lru_cache(maxsize=128)
def _noise_kernel(rate: int, low: float, high: float) -> Signal:
    half = math.ceil(rate * 0.012)
    size = 1 << (max(4096, 8 * half) - 1).bit_length()
    frequencies = np.fft.rfftfreq(size, 1 / rate)
    shape = (frequencies / max(low, 1)) ** 2
    shape = shape / (1 + shape) / (1 + (frequencies / high) ** 4)
    shape *= nyquist_gain(frequencies, rate)
    kernel = kernel_from_magnitude(shape, half)
    # Restore the exact DC null after windowing, without changing the passband.
    window = np.kaiser(len(kernel), 10)
    kernel -= np.sum(kernel) * window / np.sum(window)
    kernel.flags.writeable = False
    return kernel


def colored_noise(frames: int, rate: int, seed: int, low: float, high: float) -> Signal:
    """Stationary seeded noise whose attack never depends on the note's length.

    A generated FIR shapes white noise with deterministic prehistory. Whole
    processing blocks are generated even for short notes, so extending a tail
    cannot rewrite the preceding noise or wrap the end back onto the attack.
    """
    if frames == 0:
        return np.zeros(0)
    kernel = _noise_kernel(rate, low, high)
    history = len(kernel) - 1
    size = 1 << (max(4096, len(kernel) * 2) - 1).bit_length()
    block = size - history
    count = math.ceil((frames + history) / block) * block
    noise = np.random.Generator(np.random.PCG64(seed)).standard_normal(count)
    return convolve_causal(noise, kernel)[history : history + frames] * 0.3


@lru_cache(maxsize=128)
def _sideband_kernel(cutoff: float, rate: int) -> Signal:
    half = math.ceil(5 * rate / max(cutoff * 0.1, rate * 0.005))
    size = 1 << (max(4096, 8 * half) - 1).bit_length()
    bins = np.fft.rfftfreq(size, 1 / rate)
    shoulder = np.clip((bins / cutoff - 0.9) / 0.1, 0, 1)
    kernel = kernel_from_magnitude(0.5 + 0.5 * np.cos(np.pi * shoulder), half)
    kernel /= np.sum(kernel)
    kernel.flags.writeable = False
    return kernel


def modulate_noise(
    noise: Signal, phase: Signal, maximum_frequency: float, rate: int, depth: float
) -> Signal:
    """Add pitch-synchronous texture without folding the noise sidebands.

    Only the modulated component is low-passed. The original breath/friction
    noise keeps its full bandwidth. A cosine shoulder below the sideband limit
    leaves space for the slowly evolving phase used by acoustic voices.
    """
    cutoff = 0.49 * rate - maximum_frequency
    if not len(noise) or cutoff <= 0 or depth == 0:
        return noise
    band_limited = convolve_causal(noise, _sideband_kernel(cutoff, rate))
    return noise + depth * band_limited * np.sin(phase)


def slow_variation(t: Signal, seed: int, speed: float = 1) -> Signal:
    """Bounded smooth variation with a duration-independent seeded trajectory."""
    rng = np.random.Generator(np.random.PCG64(seed))
    frequencies = rng.uniform([0.37, 0.91, 1.9], [0.7, 1.5, 2.7]) * speed
    phases = rng.uniform(-np.pi, np.pi, 3)
    return sum(
        weight * np.sin(2 * np.pi * f * t + phase)
        for weight, f, phase in zip((0.55, 0.3, 0.15), frequencies, phases, strict=True)
    )


@lru_cache(maxsize=48)
def _body_kernel(rate: int, modes: tuple[tuple[float, float, float], ...]) -> Signal:
    """Analytic damped modes: frequency Hz, T60 seconds, relative gain."""
    frames = max(2, math.ceil(min(0.35, max(mode[1] for mode in modes)) * rate))
    t = np.arange(frames) / rate
    kernel = np.zeros(frames)
    for frequency, decay, gain in modes:
        if frequency < 0.49 * rate:
            mode = np.sin(2 * np.pi * frequency * t) * np.exp(-math.log(1000) * t / decay)
            mode /= max(float(np.sum(np.abs(mode))), 1e-12)
            kernel += gain * mode
    fade = min(frames, max(2, round(0.01 * rate)))
    kernel[-fade:] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fade))
    kernel /= max(float(np.sum(np.abs(kernel))), 1e-12)
    kernel.flags.writeable = False
    return kernel


def resonant_body(
    signal: Signal, rate: int, modes: tuple[tuple[float, float, float], ...], wet: float = 0.2
) -> Signal:
    """Causal, bounded coloration driven by the voice, with no recorded IR.

    Block overlap-add computes linear convolution; it never wraps the end of
    a note onto its attack. The score's note gate still limits the output tail.
    """
    if not modes or not len(signal) or wet == 0:
        return signal
    kernel = _body_kernel(rate, modes)
    size = 1 << (max(4096, 2 * len(kernel)) - 1).bit_length()
    block = size - len(kernel) + 1
    response = np.fft.rfft(kernel, n=size)
    result = np.zeros(len(signal))
    for start in range(0, len(signal), block):
        part = signal[start : start + block]
        convolved = np.fft.irfft(np.fft.rfft(part, n=size) * response, n=size)
        end = min(len(signal), start + len(part) + len(kernel) - 1)
        result[start:end] += convolved[: end - start]
    return (1 - wet) * signal + wet * result
