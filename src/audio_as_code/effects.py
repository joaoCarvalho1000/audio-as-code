"""Bounded, deterministic effects made entirely from code-generated delay networks."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from .model import Delay, Effect, Reverb

Audio = NDArray[np.float32]


def effects_tail(effects: tuple[Effect, ...]) -> float:
    return sum(
        (
            effect.time_seconds * (effect.repeats if effect.feedback else 1)
            if isinstance(effect, Delay)
            else effect.decay_seconds + 0.1
        )
        for effect in effects
        if effect.mix
    )


def _reverb_kernel(effect: Reverb, rate: int, channel: int) -> NDArray[np.float64]:
    """Four decaying combs and two short finite all-pass diffusers, analytically generated."""
    frames = math.ceil((effect.decay_seconds + 0.1) * rate) + 1
    impulse = np.zeros(frames)
    for seconds in (0.0297, 0.0371, 0.0411, 0.0437):
        delay = max(1, round((seconds + channel * 0.0013) * rate))
        positions = np.arange(delay, frames, delay)
        gains = np.power(10.0, -3 * positions / (rate * effect.decay_seconds))
        impulse[positions] += gains / 4
    # Finite expansion of (-g + z^-d)/(1 - g*z^-d); twelve repeats per diffuser.
    for seconds in (0.0031, 0.0053):
        delay = max(1, round((seconds + channel * 0.0002) * rate))
        source = impulse.copy()
        impulse *= -0.5
        for repeat in range(1, 13):
            offset = repeat * delay
            if offset >= frames:
                break
            impulse[offset:] += source[:-offset] * (0.75 * 0.5 ** (repeat - 1))
    fade = min(frames, max(2, round(0.01 * rate)))
    impulse[-fade:] *= np.linspace(1, 0, fade)
    return impulse


def _convolve(source: Audio, kernel: NDArray[np.float64]) -> Audio:
    """Overlap-add convolution keeps working memory independent of song duration."""
    block = 1 << max(16, (len(kernel) - 1).bit_length())
    size = block * 2
    spectrum = np.fft.rfft(kernel, n=size)
    result = np.zeros(len(source), dtype=np.float32)
    for start in range(0, len(source), block):
        chunk = source[start : start + block]
        filtered = np.fft.irfft(np.fft.rfft(chunk, n=size) * spectrum, n=size)
        count = min(len(source) - start, len(chunk) + len(kernel) - 1)
        result[start : start + count] += filtered[:count].astype(np.float32)
    return result


def apply_effects(audio: Audio, effects: tuple[Effect, ...], rate: int) -> Audio:
    """Apply a serial chain to an already tail-padded stereo buffer."""
    for effect in effects:
        if effect.mix == 0:
            continue
        wet = np.zeros_like(audio)
        if isinstance(effect, Delay):
            for repeat in range(1, effect.repeats + 1):
                if repeat > 1 and effect.feedback == 0:
                    break
                offset = round(effect.time_seconds * repeat * rate)
                if offset >= len(audio):
                    break
                wet[offset:] += audio[:-offset] * effect.feedback ** (repeat - 1)
        else:
            for channel in range(2):
                wet[:, channel] = _convolve(
                    audio[:, channel], _reverb_kernel(effect, rate, channel)
                )
        audio = audio * (1 - effect.mix) + wet * effect.mix
    return audio
