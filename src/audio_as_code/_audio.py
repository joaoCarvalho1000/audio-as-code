"""PCM WAV encoding and signal measurements, independent of score and synthesis."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

Audio = NDArray[np.float32]
WavFormat = Literal["pcm16", "pcm24", "float32"]


def _validate_wav_format(wav_format: WavFormat) -> None:
    if wav_format not in ("pcm16", "pcm24", "float32"):
        raise ValueError("wav_format must be pcm16, pcm24, or float32")


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


def _write_wav(path: Path, audio: Audio, rate: int, wav_format: WavFormat = "pcm16") -> None:
    _validate_wav_format(wav_format)
    if not np.all(np.isfinite(audio)):
        raise ValueError("WAV output must contain only finite samples")
    path.parent.mkdir(parents=True, exist_ok=True)
    if wav_format == "float32":
        # WAVE_FORMAT_IEEE_FLOAT with WAVEFORMATEX and the non-PCM fact chunk.
        size = audio.size * 4
        with path.open("wb") as stream:
            stream.write(b"RIFF" + struct.pack("<I", 50 + size) + b"WAVE")
            stream.write(b"fmt " + struct.pack("<IHHIIHHH", 18, 3, 2, rate, rate * 8, 8, 32, 0))
            stream.write(b"fact" + struct.pack("<II", 4, len(audio)))
            stream.write(b"data" + struct.pack("<I", size))
            for start in range(0, len(audio), 65536):
                stream.write(audio[start : start + 65536].astype("<f4").tobytes())
        return
    if wav_format == "pcm24":
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(3)
            stream.setframerate(rate)
            for start in range(0, len(audio), 65536):
                # float64 avoids rounding max positive float32 to 2**23.
                pcm = np.clip(
                    np.rint(audio[start : start + 65536].astype(np.float64) * 8388608),
                    -8388608,
                    8388607,
                ).astype("<i4")
                packed = pcm.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
                stream.writeframesraw(packed)
        return
    pcm = np.clip(np.rint(audio * 32768), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(pcm.tobytes())


def analyze_wav(path: str | Path) -> dict:
    """Measure 16/24-bit PCM or 32-bit float WAV in bounded blocks.

    Peak is sample peak, not true peak; RMS is not integrated loudness (LUFS).
    Float full_scale_samples counts abs(sample) >= 1, without implying clipping.
    """
    metadata = _wav_header(Path(path))
    if metadata[0] == 3:
        return _analyze_float(Path(path), metadata)
    peak = 0
    squares = 0.0
    count = 0
    clipped = 0
    try:
        stream = wave.open(str(path), "rb")
    except RuntimeError as error:
        # The stdlib RIFF parser can raise RuntimeError when an ancillary
        # chunk declares a seek beyond its enclosing chunk.
        raise wave.Error("WAV is malformed: invalid RIFF chunk layout") from error
    with stream:
        width = stream.getsampwidth()
        if width not in (2, 3) or stream.getcomptype() != "NONE":
            raise ValueError("analysis supports 16/24-bit PCM and 32-bit float WAV files")
        channels, rate, frames = stream.getnchannels(), stream.getframerate(), stream.getnframes()
        if rate <= 0:
            raise ValueError("WAV sample rate must be positive")
        # A frame contains one sample per channel, and the channel count comes
        # from the file. Bound bytes as well as frames before allocating float64
        # analysis buffers; retain the existing mono/stereo block sizes.
        block_frames = min(65536, max(1, 262144 // (channels * width)))
        scale = 2 ** (8 * width - 1)
        while data := stream.readframes(block_frames):
            if len(data) % (width * channels):
                raise ValueError("WAV is truncated or malformed: incomplete PCM frame")
            if width == 2:
                pcm = np.frombuffer(data, dtype="<i2").astype(np.float64)
            else:
                packed = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
                values = packed[:, 0] | (packed[:, 1] << 8) | (packed[:, 2] << 16)
                pcm = ((values ^ 8388608) - 8388608).astype(np.float64)
            count += pcm.size
            peak = max(peak, float(np.max(np.abs(pcm))))
            squares += float(np.sum(pcm * pcm))
            clipped += int(np.count_nonzero((pcm >= scale - 1) | (pcm <= -scale)))
    if count != frames * channels:
        raise ValueError("WAV is truncated: actual samples do not match the file header")
    rms = math.sqrt(squares / count) / scale if count else 0.0
    amplitude = peak / scale
    report = {
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
    if width == 3:
        report["wav_format"] = "pcm24"
    return report


def _wav_header(path: Path) -> tuple[int, int, int, int, int]:
    """Bounded RIFF scan; return tag, channels, rate, data offset and byte count."""
    with path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise wave.Error("WAV is malformed: expected RIFF/WAVE header")
        riff_end = 8 + struct.unpack_from("<I", header, 4)[0]
        file_size = path.stat().st_size
        fmt = None
        while stream.tell() < riff_end:
            chunk = stream.read(8)
            if len(chunk) != 8:
                raise wave.Error("WAV is malformed: invalid RIFF chunk layout")
            name, size = struct.unpack("<4sI", chunk)
            offset = stream.tell()
            if offset + size > riff_end:
                raise wave.Error("WAV is malformed: invalid RIFF chunk layout")
            if name == b"fmt ":
                if fmt is not None or size < 16:
                    raise wave.Error("WAV is malformed: invalid format chunk")
                data = stream.read(min(size, 18))
                if len(data) < min(size, 18):
                    raise ValueError("WAV is truncated: incomplete format chunk")
                tag, channels, rate, byte_rate, alignment, bits = struct.unpack_from(
                    "<HHIIHH", data
                )
                if rate == 0:
                    raise ValueError("WAV sample rate must be positive")
                if channels == 0:
                    raise ValueError("WAV channel count must be positive")
                if (tag, bits) not in ((1, 16), (1, 24), (3, 32)):
                    raise ValueError("analysis supports 16/24-bit PCM and 32-bit float WAV files")
                if alignment != channels * (bits // 8) or byte_rate != rate * alignment:
                    raise ValueError("WAV is malformed: inconsistent frame alignment or byte rate")
                if tag == 3 and (size < 18 or struct.unpack_from("<H", data, 16)[0] != 0):
                    raise ValueError("WAV float format requires a zero-size WAVEFORMATEX extension")
                fmt = (tag, channels, rate)
            elif name == b"data":
                if fmt is None:
                    raise wave.Error("WAV is malformed: data precedes format")
                if offset + size > file_size:
                    raise ValueError(
                        "WAV is truncated: actual samples do not match the file header"
                    )
                return (*fmt, offset, size)
            if offset + size + (size & 1) > file_size:
                raise wave.Error("WAV is malformed: invalid RIFF chunk layout")
            stream.seek(offset + size + (size & 1))
    raise wave.Error("WAV is malformed: missing data chunk")


def _analyze_float(path: Path, metadata: tuple[int, int, int, int, int]) -> dict:
    _, channels, rate, offset, size = metadata
    if size % (4 * channels):
        raise ValueError("WAV is truncated or malformed: incomplete float frame")
    peak, squares, count, full_scale = 0.0, 0.0, 0, 0
    with path.open("rb") as stream:
        stream.seek(offset)
        remaining = size
        while remaining:
            data = stream.read(min(262144, remaining))
            if not data or len(data) % 4:
                raise ValueError("WAV is truncated: incomplete float sample")
            values = np.frombuffer(data, dtype="<f4").astype(np.float64)
            if not np.all(np.isfinite(values)):
                raise ValueError("WAV contains non-finite float samples")
            peak = max(peak, float(np.max(np.abs(values))))
            squares += float(np.sum(values * values))
            full_scale += int(np.count_nonzero(np.abs(values) >= 1))
            count += len(values)
            remaining -= len(data)
    rms = math.sqrt(squares / count) if count else 0.0
    frames = size // (4 * channels)
    return {
        "sample_rate": rate,
        "channels": channels,
        "frames": frames,
        "duration_seconds": frames / rate,
        "peak": peak,
        "rms": rms,
        "peak_dbfs": 20 * math.log10(peak) if peak else None,
        "rms_dbfs": 20 * math.log10(rms) if rms else None,
        "full_scale_samples": full_scale,
        "silent": peak == 0,
        "wav_format": "float32",
    }
