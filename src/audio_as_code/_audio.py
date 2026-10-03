"""PCM WAV encoding and signal measurements, independent of score and synthesis."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

Audio = NDArray[np.float32]


def _metrics(audio: Audio, rate: int) -> dict:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) if audio.size else 0.0
    return {
        "sample_rate": rate,
        "channels": audio.shape[1],
        "frames": len(audio),
        "duration_seconds": len(audio) / rate,
        "peak": peak,
        "rms": rms,
        "peak_dbfs": 20 * math.log10(peak) if peak > 0 else None,
        "rms_dbfs": 20 * math.log10(rms) if rms > 0 else None,
        "clipped_samples": int(np.count_nonzero(np.abs(audio) >= 1)),
        "silent": peak == 0,
    }


def _write_wav(path: Path, audio: Audio, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.rint(audio * 32768), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(pcm.tobytes())


def analyze_wav(path: str | Path) -> dict:
    """Measure a 16-bit PCM WAV in blocks. These are signal checks, not music criticism."""
    peak = 0
    squares = 0.0
    count = 0
    clipped = 0
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2 or stream.getcomptype() != "NONE":
            raise ValueError("analysis supports uncompressed 16-bit PCM WAV files")
        channels, rate, frames = stream.getnchannels(), stream.getframerate(), stream.getnframes()
        if rate <= 0:
            raise ValueError("WAV sample rate must be positive")
        # A frame contains one sample per channel, and the channel count comes
        # from the file. Bound bytes as well as frames before allocating float64
        # analysis buffers; retain the existing mono/stereo block sizes.
        block_frames = min(65536, max(1, 131072 // channels))
        while data := stream.readframes(block_frames):
            if len(data) % (2 * channels):
                raise ValueError("WAV is truncated or malformed: incomplete PCM frame")
            pcm = np.frombuffer(data, dtype="<i2").astype(np.float64)
            count += pcm.size
            peak = max(peak, float(np.max(np.abs(pcm))))
            squares += float(np.sum(pcm * pcm))
            clipped += int(np.count_nonzero((pcm >= 32767) | (pcm <= -32768)))
    if count != frames * channels:
        raise ValueError("WAV is truncated: actual samples do not match the file header")
    rms = math.sqrt(squares / count) / 32768 if count else 0.0
    amplitude = peak / 32768
    return {
        "sample_rate": rate,
        "channels": channels,
        "frames": frames,
        "duration_seconds": frames / rate,
        "peak": amplitude,
        "rms": rms,
        "peak_dbfs": 20 * math.log10(amplitude) if amplitude else None,
        "rms_dbfs": 20 * math.log10(rms) if rms else None,
        "full_scale_samples": clipped,
        "silent": peak == 0,
    }
