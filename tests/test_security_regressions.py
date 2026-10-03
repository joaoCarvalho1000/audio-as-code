"""Regression coverage for confirmed local file-processing security boundaries."""

import math
import struct
import wave

import pytest

from audio_as_code import analyze_wav


@pytest.mark.parametrize("channels", [1, 2, 8, 32767])
def test_wav_analysis_bounds_reads_independently_of_channel_count(tmp_path, monkeypatch, channels):
    path = tmp_path / "multichannel.wav"
    # Five frames at the largest valid 16-bit PCM block alignment cross the
    # bounded read size without needing a large fixture or stressing host RAM.
    samples = [0, 32767, -32768, 16384, -16384]
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(22050)
        stream.writeframes(b"".join(struct.pack("<h", sample) * channels for sample in samples))

    requested_bytes = []
    original_read = wave.Wave_read.readframes

    def record_read(stream, frames):
        requested_bytes.append(frames * stream.getnchannels() * stream.getsampwidth())
        return original_read(stream, frames)

    monkeypatch.setattr(wave.Wave_read, "readframes", record_read)
    report = analyze_wav(path)

    assert max(requested_bytes) <= 256 * 1024
    assert report["channels"] == channels
    assert report["frames"] == len(samples)
    assert report["peak"] == 1
    assert report["full_scale_samples"] == 2 * channels
    assert report["rms"] == pytest.approx(
        math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768
    )
