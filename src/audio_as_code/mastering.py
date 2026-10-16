"""Offline bus dynamics and reconstructed peak metering, using generated FIRs.

The meter estimates intersample peaks; it is not a certified hardware meter.
Oversampled work buffers are bounded independently of the song duration.
"""

from __future__ import annotations

import math

import numpy as np

from ._fir import convolve_causal
from ._render_control import CancelCallback, _RenderControl
from .model import BusCompressor, Mastering, TruePeakLimiter

_BLOCK = 32768
_HALF = 48
_SAFETY_DB = 0.1


def _db(value: float) -> float | None:
    return 20 * math.log10(value) if value > 0 else None


def _validate_audio(audio: np.ndarray, rate: int) -> np.ndarray:
    if type(rate) is not int or rate not in (22050, 44100, 48000):
        raise ValueError("true-peak sample_rate must be 22050, 44100, or 48000")
    if not isinstance(audio, np.ndarray) or audio.dtype.kind != "f":
        raise ValueError("audio must be a floating-point NumPy array")
    if audio.ndim not in (1, 2) or (audio.ndim == 2 and audio.shape[1] not in (1, 2)):
        raise ValueError("audio must be mono or stereo")
    if not 1 <= len(audio) <= 300 * rate:
        raise ValueError("true-peak measurement requires 1 sample to 300 seconds")
    if not np.isfinite(audio).all() or np.max(np.abs(audio)) > np.finfo(np.float32).max:
        raise ValueError("audio must contain finite samples within the float32 numeric range")
    return audio[:, None] if audio.ndim == 1 else audio


def _resample_kernel(factor: int, *, down: bool = False) -> np.ndarray:
    taps = np.arange(-_HALF * factor, _HALF * factor + 1)
    cutoff = 0.94 if down else 1.0
    kernel = np.sinc(taps * cutoff / factor) * np.kaiser(len(taps), 8.6)
    return kernel * ((1 if down else factor) / kernel.sum())


def _centered(signal: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    half = len(kernel) // 2
    return convolve_causal(np.pad(signal, (0, half)), kernel)[half:]


def _high_block(audio: np.ndarray, start: int, stop: int, factor: int) -> np.ndarray:
    """Reconstruct a range with input halo and silence beyond the signal boundaries."""
    lo, hi = max(0, start - _HALF), min(len(audio), stop + _HALF)
    result = np.empty(((stop - start) * factor, audio.shape[1]))
    kernel = _resample_kernel(factor)
    for channel in range(audio.shape[1]):
        expanded = np.zeros((hi - lo) * factor)
        expanded[::factor] = audio[lo:hi, channel]
        high = _centered(expanded, kernel)
        result[:, channel] = high[(start - lo) * factor : (stop - lo) * factor]
    return result


def measure_true_peak(
    audio: np.ndarray,
    sample_rate: int,
    *,
    oversample: int = 4,
    cancel: CancelCallback | None = None,
) -> dict:
    """Return a JSON-safe FIR reconstructed peak estimate, including sample peaks."""
    control = _RenderControl(cancel=cancel)
    control.check()
    audio = _validate_audio(audio, sample_rate)
    if type(oversample) is not int or oversample not in (4, 8):
        raise ValueError("oversample must be 4 or 8")
    peaks = np.max(np.abs(audio), axis=0).astype(np.float64)
    for start in range(0, len(audio), _BLOCK):
        control.check()
        high = _high_block(audio, start, min(len(audio), start + _BLOCK), oversample)
        peaks = np.maximum(peaks, np.max(np.abs(high), axis=0))
    control.check()
    peak = float(np.max(peaks))
    return {
        "true_peak": peak,
        "true_peak_dbtp": _db(peak),
        "channel_true_peak_dbtp": [_db(float(value)) for value in peaks],
        "true_peak_method": "generated_kaiser_sinc_96_sample_support",
        "true_peak_oversample": oversample,
    }


def _compress(audio: np.ndarray, rate: int, settings: BusCompressor) -> tuple[np.ndarray, dict]:
    settings = BusCompressor.model_validate(settings.model_dump())
    if settings.ratio == 1:
        return audio * 10 ** (settings.makeup_db / 20), {"max_gain_reduction_db": 0.0}
    levels = 20 * np.log10(np.maximum(np.max(np.abs(audio), axis=1), 1e-30))
    over = levels - settings.threshold_dbfs
    knee = settings.knee_db
    reduction = np.maximum(over, 0) * (1 - 1 / settings.ratio)
    if knee:
        inside = np.abs(over) < knee / 2
        reduction[inside] = (1 - 1 / settings.ratio) * (over[inside] + knee / 2) ** 2 / (2 * knee)
        reduction[over <= -knee / 2] = 0
    attack = math.exp(-1 / (rate * settings.attack_seconds))
    release = math.exp(-1 / (rate * settings.release_seconds))
    state = 0.0
    for i, requested in enumerate(reduction.tolist()):
        coefficient = attack if requested > state else release
        state = coefficient * state + (1 - coefficient) * requested
        reduction[i] = state
    gain = 10 ** ((settings.makeup_db - reduction) / 20)
    return (audio * gain[:, None]).astype(np.float32), {
        "max_gain_reduction_db": float(reduction.max()),
    }


def _future_min(values: np.ndarray, size: int) -> np.ndarray:
    """O(n) sliding minimum with vectorized prefix/suffix scans of window-sized tiles."""
    n = len(values)
    padded = np.pad(values, (0, size + (-n % size)), constant_values=1).reshape(-1, size)
    prefix = np.minimum.accumulate(padded, axis=1).ravel()
    suffix = np.minimum.accumulate(padded[:, ::-1], axis=1)[:, ::-1].ravel()
    return np.minimum(suffix[:n], prefix[size - 1 : size - 1 + n])


def _safety_peak(audio: np.ndarray, rate: int) -> float:
    peak = measure_true_peak(audio, rate, oversample=8)["true_peak"]
    # Resamplers differ in their treatment of a discontinuous file boundary.
    # Also check reflected edges, conservatively covering startup extrapolation.
    for edge in (audio[:96], audio[-96:]):
        reflected = np.pad(edge, ((48, 48), (0, 0)), mode="reflect")
        peak = max(peak, measure_true_peak(reflected, rate, oversample=8)["true_peak"])
    return peak


def _limit(audio: np.ndarray, rate: int, settings: TruePeakLimiter) -> tuple[np.ndarray, dict]:
    factor = settings.oversample
    # Absolute reserve bounds reconstructed PCM16 rounding noise even at quiet ceilings.
    ceiling = 10 ** ((settings.ceiling_dbtp - _SAFETY_DB) / 20) - 2 / 32768
    required = np.empty(len(audio))
    for start in range(0, len(audio), _BLOCK):
        stop = min(len(audio), start + _BLOCK)
        high = _high_block(audio, start, stop, factor)
        peaks = np.max(np.abs(high).reshape(stop - start, factor, -1), axis=(1, 2))
        required[start:stop] = np.minimum(1, ceiling / np.maximum(peaks, 1e-30))
    if np.all(required == 1):
        peak = _safety_peak(audio, rate)
        correction = min(1.0, ceiling / peak) if peak else 1.0
        return audio * correction, {
            "max_gain_reduction_db": -20 * math.log10(correction),
            "safety_gain": correction,
            "safety_margin_db": _SAFETY_DB,
            "pcm_rounding_reserve": 2 / 32768,
            "ceiling_dbtp": settings.ceiling_dbtp,
        }
    window = round(settings.lookahead_seconds * rate) + 1
    anticipatory = _future_min(required, window)
    recovery = math.exp(-1 / (rate * settings.release_seconds))
    state = float(anticipatory[0])
    for i, value in enumerate(anticipatory.tolist()):
        state = min(value, recovery * state + (1 - recovery))
        anticipatory[i] = state
    # Every value in this trailing average already looked ahead to the current peak.
    padded = np.pad(anticipatory, (window - 1, 0), mode="edge")
    cumulative = np.concatenate(([0.0], np.cumsum(padded, dtype=np.float64)))
    gain = np.minimum(required, (cumulative[window:] - cumulative[:-window]) / window)
    result = np.empty_like(audio)
    kernel = _resample_kernel(factor, down=True)
    for start in range(0, len(audio), _BLOCK):
        stop = min(len(audio), start + _BLOCK)
        lo, hi = max(0, start - _HALF), min(len(audio), stop + _HALF)
        high = _high_block(audio, lo, hi, factor)
        high *= np.repeat(gain[lo:hi], factor)[:, None]
        for channel in range(audio.shape[1]):
            low = _centered(high[:, channel], kernel)[::factor]
            result[start:stop, channel] = low[start - lo : stop - lo]
    # Reconstructed peaks can grow during decimation. Correct using an independent pass.
    peak = _safety_peak(result, rate)
    correction = min(1.0, ceiling / peak) if peak else 1.0
    result *= correction
    return result, {
        "max_gain_reduction_db": -20 * math.log10(max(float(gain.min()) * correction, 1e-30)),
        "safety_gain": correction,
        "safety_margin_db": _SAFETY_DB,
        "pcm_rounding_reserve": 2 / 32768,
        "ceiling_dbtp": settings.ceiling_dbtp,
    }


def process_master(audio, rate, settings: Mastering, target, sample_ceiling, control, normalize):
    """Return processed audio, constant delivery gain, dynamics and optional LUFS reports."""
    from .loudness import _loudness_gain, measure_loudness

    report = {"settings": settings.model_dump(), "gain_scope": "constant_delivery_gain_only"}
    source = audio
    if settings.compressor is not None:
        source, report["compressor"] = _compress(source, rate, settings.compressor)
    control.check()
    before = measure_loudness(source, rate, true_peak=False) if target is not None else None
    before_lufs = before["integrated_lufs"] if before is not None else None
    loudness = None
    if settings.limiter is None:
        gain = 1.0
        if target is not None:
            gain, loudness = _loudness_gain(source, rate, target, sample_ceiling)
        elif normalize:
            peak = float(np.max(np.abs(source)))
            gain = min(1.0, 0.95 / peak) if peak else 1.0
        return source * gain, gain, report, loudness

    def candidate(db):
        control.check()
        gain = 10 ** (db / 20)
        result, limited = _limit(source * gain, rate, settings.limiter)
        measured = measure_loudness(result, rate, true_peak=False) if target is not None else None
        return result, gain * limited["safety_gain"], limited, measured

    drive = max(-120.0, min(60.0, target - before_lufs)) if before_lufs is not None else 0.0
    best = candidate(drive)
    iterations = 1
    if before_lufs is not None:
        low, high = -120.0, 60.0
        current = best
        value = current[3]["integrated_lufs"]
        best_error = abs(value - target) if value is not None else float("inf")
        for _ in range(23):
            value = current[3]["integrated_lufs"]
            error = abs(value - target) if value is not None else float("inf")
            if error <= 0.05:
                break
            if value is None or value < target:
                low = drive
            else:
                high = drive
            drive = (low + high) / 2
            current = candidate(drive)
            iterations += 1
            trial_value = current[3]["integrated_lufs"]
            trial_error = abs(trial_value - target) if trial_value is not None else float("inf")
            if trial_error < best_error:
                best, best_error = current, trial_error
    result, gain, report["limiter"], measured = best
    report["iterations"] = iterations
    report["delivery_gain_db"] = _db(gain)
    if measured is not None:
        loudness = {
            **measured,
            "before_lufs": before_lufs,
            "target_lufs": target,
            "requested_gain_db": target - before_lufs if before_lufs is not None else 0,
            "applied_gain_db": _db(gain),
            "true_peak_ceiling_dbtp": settings.limiter.ceiling_dbtp,
            "peak_limited": report["limiter"]["max_gain_reduction_db"] > 0.001,
        }
    return result, gain, report, loudness


def measure_exported(path, wav_format: str, *, loudness: bool = False) -> dict:
    """Remeasure a staged engine WAV, including its actual quantization."""
    from ._audio import _wav_header
    from .loudness import measure_loudness

    _, channels, rate, offset, size = _wav_header(path)
    width = {"pcm16": 2, "pcm24": 3, "float32": 4}[wav_format]
    frames = size // (channels * width)
    audio = np.empty((frames, channels), dtype=np.float32)
    with path.open("rb") as stream:
        stream.seek(offset)
        for start in range(0, frames, _BLOCK):
            stop = min(frames, start + _BLOCK)
            data = stream.read((stop - start) * channels * width)
            if wav_format == "float32":
                values = np.frombuffer(data, dtype="<f4")
            elif wav_format == "pcm16":
                values = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768
            else:
                packed = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
                values = packed[:, 0] | (packed[:, 1] << 8) | (packed[:, 2] << 16)
                values = ((values ^ 8388608) - 8388608).astype(np.float32) / 8388608
            audio[start:stop] = values.reshape(-1, channels)
    report = measure_true_peak(audio, rate, oversample=8)
    if loudness and frames >= round(0.4 * rate):
        report["integrated_lufs"] = measure_loudness(audio, rate, true_peak=False)[
            "integrated_lufs"
        ]
    return report
