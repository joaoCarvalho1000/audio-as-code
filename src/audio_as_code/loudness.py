"""Optional BS.1770-4 integrated loudness via pyloudnorm's DeMan filters."""

from __future__ import annotations

import math
from importlib.metadata import version

import numpy as np

from ._audio import Audio
from ._export_rules import MAX_RENDER_SECONDS


def _meter(sample_rate: int):
    try:
        import pyloudnorm
    except ImportError as error:
        raise ValueError(
            "Loudness measurement requires the optional extra: "
            'pip install "audio-as-code[loudness]" '
            "(checkout: uv sync --extra loudness)."
        ) from error
    return pyloudnorm.Meter(sample_rate, filter_class="DeMan", block_size=0.400)


def _validate_target(
    target_lufs: float | None,
    peak_ceiling_dbfs: float,
    normalize: bool,
    sample_rate: int,
    frames: int,
) -> None:
    for value, name, low, high in (
        (peak_ceiling_dbfs, "peak_ceiling_dbfs", -60, 0),
        (target_lufs, "target_lufs", -70, 0),
    ):
        if value is None and name == "target_lufs":
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not low <= value <= high
        ):
            raise ValueError(f"{name} must be a finite number from {low} to {high}")
    if target_lufs is None:
        if peak_ceiling_dbfs != -1.0:
            raise ValueError("peak_ceiling_dbfs requires target_lufs")
        return
    if not normalize:
        raise ValueError("target_lufs cannot be combined with normalize=False")
    if frames < math.ceil(0.4 * sample_rate):
        raise ValueError("integrated loudness requires at least 0.4 seconds of audio")
    _meter(sample_rate)  # Fail before expensive synthesis or any file writes.


def measure_loudness(audio: Audio, sample_rate: int) -> dict:
    """Measure mono/stereo integrated LUFS, including the absolute/relative gates.

    Accepts 0.4 to 300 seconds at the engine's 22050/44100/48000 Hz rates.
    Silence or signals below the loudness gate return integrated_lufs=None.
    This does not measure true peak, loudness range, or streaming delivery compliance.
    """
    if (
        isinstance(sample_rate, bool)
        or not isinstance(sample_rate, int)
        or sample_rate not in (22050, 44100, 48000)
    ):
        raise ValueError("loudness sample_rate must be 22050, 44100, or 48000")
    if not isinstance(audio, np.ndarray) or audio.dtype.kind != "f":
        raise ValueError("loudness audio must be a floating-point NumPy array")
    if audio.ndim not in (1, 2) or (audio.ndim == 2 and audio.shape[1] not in (1, 2)):
        raise ValueError("loudness audio must be mono or stereo")
    if len(audio) < math.ceil(0.4 * sample_rate):
        raise ValueError("integrated loudness requires at least 0.4 seconds of audio")
    if len(audio) > MAX_RENDER_SECONDS * sample_rate:
        raise ValueError(f"loudness measurement is limited to {MAX_RENDER_SECONDS} seconds")
    if not np.all(np.isfinite(audio)):
        raise ValueError("loudness audio must contain only finite samples")
    if np.max(np.abs(audio)) > np.finfo(np.float32).max:
        raise ValueError("loudness audio exceeds the float32 audio numeric range")
    meter = _meter(sample_rate)
    # BS.1770 uses complete 400 ms blocks on 100 ms hops. pyloudnorm 0.2
    # rounds its block count and otherwise includes a partial last block.
    block = sample_rate * 4 // 10
    hop = sample_rate // 10
    measured_frames = block + (len(audio) - block) // hop * hop
    # Float64 filtering avoids float32 rounding and overflow in squared energies.
    value = float(meter.integrated_loudness(audio[:measured_frames].astype(np.float64)))
    if math.isnan(value) or value == math.inf:
        raise ValueError("loudness measurement produced a non-finite result")
    return {
        "integrated_lufs": value if math.isfinite(value) else None,
        "measurable": math.isfinite(value),
        "method": "ITU-R BS.1770-4",
        "backend": "pyloudnorm",
        "backend_version": version("pyloudnorm"),
        "filter": "DeMan",
        "block_seconds": 0.4,
        "measured_frames": measured_frames,
        "trailing_frames_ignored": len(audio) - measured_frames,
    }


def _loudness_gain(
    audio: Audio, sample_rate: int, target_lufs: float, peak_ceiling_dbfs: float
) -> tuple[float, dict]:
    measured = measure_loudness(audio, sample_rate)
    before = measured["integrated_lufs"]
    desired = 10 ** ((target_lufs - before) / 20) if before is not None else 1.0
    peak = float(np.max(np.abs(audio)))
    ceiling = 10 ** (peak_ceiling_dbfs / 20)
    maximum = ceiling / peak if peak else 1.0
    limited = desired > maximum
    gain = desired
    if limited:
        # Leave one float32 step of headroom for multiplication rounding.
        gain = float(np.nextafter(np.float32(maximum), np.float32(0)))
    return gain, {
        **measured,
        "before_lufs": before,
        "target_lufs": target_lufs,
        "requested_gain_db": 20 * math.log10(desired),
        "applied_gain_db": 20 * math.log10(gain) if gain else None,
        "sample_peak_ceiling_dbfs": peak_ceiling_dbfs,
        "peak_limited": limited,
        "measurement_scope": "full_render_before_encoding",
    }
