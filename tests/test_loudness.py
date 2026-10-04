"""Optional integrated loudness, bounded gain, and unchanged default imports."""

import builtins
import json
import subprocess
import sys
import warnings

import numpy as np
import pytest

from audio_as_code import Note, Song, Track, render, render_audio
from audio_as_code.loudness import measure_loudness
from audio_as_code.render import render_preview_audio


@pytest.fixture
def loudness_backend():
    return pytest.importorskip("pyloudnorm")


def tone(rate, seconds=2, amplitude=0.1):
    signal = amplitude * np.sin(2 * np.pi * 1000 * np.arange(round(seconds * rate)) / rate)
    return np.column_stack((signal, signal)).astype(np.float32)


def song(rate=22050):
    return Song(
        sample_rate=rate,
        beats=4,
        tracks=[Track(name="Tone", instrument="sine", notes=[Note(duration=4)])],
    )


def test_default_import_and_render_do_not_import_optional_backend():
    code = """
import sys
from audio_as_code import Song, Track, render_audio
result = render_audio(Song(beats=1, tracks=[Track(name='Silent')]))
assert 'pyloudnorm' not in sys.modules
assert 'scipy' not in sys.modules
assert 'loudness' not in result.report
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


def test_missing_extra_fails_before_any_output(tmp_path, monkeypatch):
    original_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "pyloudnorm":
            raise ImportError("optional dependency deliberately unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(ValueError, match=r"audio-as-code\[loudness\]"):
        render(song(), tmp_path / "missing" / "mix.wav", target_lufs=-18)
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"target_lufs": -18, "normalize": False}, "normalize=False"),
        ({"target_lufs": float("nan")}, "target_lufs"),
        ({"target_lufs": True}, "target_lufs"),
        ({"target_lufs": -71}, "target_lufs"),
        ({"target_lufs": 1}, "target_lufs"),
        ({"target_lufs": "-18"}, "target_lufs"),
        ({"peak_ceiling_dbfs": -2}, "requires target_lufs"),
        ({"target_lufs": -18, "peak_ceiling_dbfs": float("inf")}, "peak_ceiling_dbfs"),
        ({"target_lufs": -18, "peak_ceiling_dbfs": 1}, "peak_ceiling_dbfs"),
        ({"target_lufs": -18, "peak_ceiling_dbfs": -61}, "peak_ceiling_dbfs"),
        ({"target_lufs": -18, "peak_ceiling_dbfs": True}, "peak_ceiling_dbfs"),
    ],
)
def test_invalid_loudness_options_preserve_destinations(tmp_path, kwargs, match):
    path = tmp_path / "mix.wav"
    path.write_bytes(b"existing")
    with pytest.raises(ValueError, match=match):
        render(song(), path, **kwargs)
    assert path.read_bytes() == b"existing"


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_known_stereo_tone_and_mono_channel_weighting(rate, loudness_backend):
    audio = tone(rate)
    stereo = measure_loudness(audio, rate)
    mono = measure_loudness(audio[:, 0], rate)
    # 1 kHz, amplitude 0.1 in both front channels: approximately -20 LUFS.
    assert stereo["integrated_lufs"] == pytest.approx(-20, abs=0.1)
    assert stereo["integrated_lufs"] - mono["integrated_lufs"] == pytest.approx(
        10 * np.log10(2), abs=1e-9
    )
    assert stereo["filter"] == "DeMan" and stereo["measurable"]


@pytest.mark.parametrize("amplitude", [0, 1e-7])
def test_silence_and_below_gate_are_json_safe_without_warnings(amplitude, loudness_backend):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        measured = measure_loudness(tone(22050, amplitude=amplitude), 22050)
        quiet = song().model_copy(update={"master_gain": amplitude})
        result = render_audio(quiet, target_lufs=-18)
    assert measured["integrated_lufs"] is None and not measured["measurable"]
    assert result.report["loudness"]["achieved_lufs"] is None
    assert result.report["gain_applied"] == 1
    assert not result.report["loudness"]["target_reached"]
    json.dumps(result.report, allow_nan=False)


@pytest.mark.parametrize("target", [-30, -18])
def test_loudness_target_remeasured_and_preview_uses_full_context(target, loudness_backend):
    score = song()
    plain = render_audio(score, normalize=False)
    result = render_audio(score, target_lufs=target)
    report = result.report["loudness"]
    assert report["achieved_lufs"] == pytest.approx(target, abs=0.01)
    assert report["target_reached"] and not report["peak_limited"]
    assert (
        report["before_lufs"] == measure_loudness(plain.audio, score.sample_rate)["integrated_lufs"]
    )
    assert report["applied_gain_db"] == pytest.approx(20 * np.log10(result.report["gain_applied"]))
    preview = render_preview_audio(
        score, start_seconds=0.31, duration_seconds=0.2, target_lufs=target
    )
    first, last = round(0.31 * score.sample_rate), round(0.51 * score.sample_rate)
    np.testing.assert_array_equal(preview.audio, result.audio[first:last])
    assert preview.report["loudness"] == report


def test_peak_ceiling_limits_gain_and_stems_share_it(tmp_path, loudness_backend):
    score = song()
    result = render_audio(score, target_lufs=0, peak_ceiling_dbfs=-6)
    assert np.max(np.abs(result.audio)) <= 10 ** (-6 / 20)
    assert result.report["loudness"]["peak_limited"]
    assert not result.report["loudness"]["target_reached"]
    report = render(
        score,
        tmp_path / "mix.wav",
        stems_dir=tmp_path / "stems",
        wav_format="float32",
        target_lufs=0,
        peak_ceiling_dbfs=-6,
    )
    assert (tmp_path / "mix.wav").read_bytes() == (tmp_path / "stems" / "01.wav").read_bytes()
    assert report["loudness"] == result.report["loudness"]


@pytest.mark.parametrize(
    "audio,rate,match",
    [
        (np.zeros(100, np.float32), 22050, "0.4 seconds"),
        (np.zeros(22050, np.int16), 22050, "floating-point"),
        (np.zeros((22050, 3), np.float32), 22050, "mono or stereo"),
        (np.zeros(22050, np.float32), 32000, "sample_rate"),
        (np.zeros(22050, np.float32), 22050.0, "sample_rate"),
        (np.full(22050, np.nan, np.float32), 22050, "finite"),
    ],
)
def test_invalid_measurement_input(audio, rate, match):
    with pytest.raises(ValueError, match=match):
        measure_loudness(audio, rate)


def test_sub_block_render_rejected_before_writing(tmp_path):
    score = Song(sample_rate=22050, beats=0.25, tracks=[Track(name="Silent")])
    with pytest.raises(ValueError, match="0.4 seconds"):
        render(score, tmp_path / "missing" / "mix.wav", target_lufs=-18)
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_only_complete_gating_blocks_are_measured(rate, loudness_backend):
    short = tone(rate, seconds=0.47)
    complete = short[: round(rate * 0.4)]
    report = measure_loudness(short, rate)
    assert report["integrated_lufs"] == measure_loudness(complete, rate)["integrated_lufs"]
    assert report["measured_frames"] == len(complete)
    assert report["trailing_frames_ignored"] == len(short) - len(complete)


def test_extreme_float64_input_fails_without_numeric_warnings(loudness_backend):
    audio = np.full((22050, 2), np.finfo(np.float64).max, np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(ValueError, match="numeric range"):
            measure_loudness(audio, 22050)
