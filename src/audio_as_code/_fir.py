"""Finite generated filters with linear, causal convolution and bounded work buffers."""

from __future__ import annotations

import numpy as np


def kernel_from_magnitude(magnitude: np.ndarray, half: int) -> np.ndarray:
    """Window a symmetric frequency design and delay it into a causal FIR.

    The input contains real-FFT bins on an even-length design grid. No recorded
    response is involved. The filter delays its input by ``half`` samples.
    """
    impulse = np.fft.irfft(magnitude)
    kernel = np.concatenate((impulse[-half:], impulse[: half + 1]))
    kernel *= np.kaiser(len(kernel), 10)
    return kernel


def convolve_causal(signal: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Overlap-save convolution, retaining the input length and no circular wrap."""
    size = 1 << (max(4096, len(kernel) * 2) - 1).bit_length()
    block = size - len(kernel) + 1
    response = np.fft.rfft(kernel, n=size)
    result = np.empty(len(signal), dtype=np.float64)
    history = len(kernel) - 1
    for start in range(0, len(signal), block):
        stop = min(len(signal), start + block)
        data = np.zeros(size)
        lo = max(0, start - history)
        offset = max(0, history - start)
        data[offset : offset + stop - lo] = signal[lo:stop]
        filtered = np.fft.irfft(np.fft.rfft(data) * response, n=size)
        result[start:stop] = filtered[history : history + stop - start]
    return result
