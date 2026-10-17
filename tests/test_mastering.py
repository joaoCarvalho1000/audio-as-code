"""Bus dynamics, independent FFmpeg reference measurements, and export integration."""

import json
import os
import re
import shutil
import subprocess

import numpy as np
import pytest

from audio_as_code import (
    BusCompressor,
    Mastering,
    Note,
    Song,
    Track,
    TruePeakLimiter,
    measure_true_peak,
    render,
    render_audio,
    render_preview_audio,
)
from audio_as_code._audio import _write_wav
from audio_as_code._render_control import _RenderControl
from audio_as_code.cli import main
from audio_as_code.mastering import _compress, _future_min, _limit, process_master


@pytest.fixture
def ffmpeg():
    executable = shutil.which("ffmpeg")
    if executable is None:
        if os.environ.get("AAC_REQUIRE_FFMPEG") == "1":
            pytest.fail("FFmpeg reference validation is required")
        pytest.skip("FFmpeg unavailable; reference validation was not run")
    return executable


def reference(ffmpeg, path):
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    summary = result.stderr.rsplit("Summary:", 1)[1]
    lufs = float(re.search(r"I:\s*([-+\w.]+) LUFS", summary)[1])
    peak = float(re.search(r"Peak:\s*([-+\w.]+) dBFS", summary)[1])
    return lufs, peak


def dynamic_audio(rate):
    t = np.arange(rate * 3) / rate
    signal = 0.03 * np.sin(2 * np.pi * 440 * t)
    for at in (0.3, 0.9, 1.7, 2.6):
        offset = t - at
        signal += (
            0.8
            * np.sin(2 * np.pi * 2300 * offset)
            * np.exp(-np.maximum(offset, 0) / 0.002)
            * (offset >= 0)
        )
    return np.column_stack((signal, signal * 0.7)).astype(np.float32)


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
@pytest.mark.parametrize("kind", ["tone", "intersample", "impulse", "noise", "dynamic"])
def test_true_peak_against_ffmpeg(rate, kind, tmp_path, ffmpeg):
    t = np.arange(rate) / rate
    if kind == "tone":
        signal = 0.7 * np.sin(2 * np.pi * 1000 * t)
    elif kind == "intersample":
        signal = 0.9 * np.sin(2 * np.pi * (rate / 4) * t + np.pi / 4)
        # Compare the reconstruction in-band, excluding differing file-edge extrapolation.
        ramp = round(rate * 0.01)
        signal[:ramp] *= np.linspace(0, 1, ramp)
        signal[-ramp:] *= np.linspace(1, 0, ramp)
    elif kind == "impulse":
        signal = np.zeros(rate)
        signal[rate // 2] = 0.8
    elif kind == "noise":
        # Band-limited generated noise, avoiding differing near-Nyquist meter passbands.
        spectrum = np.fft.rfft(np.random.default_rng(37).normal(0, 0.1, rate))
        spectrum[np.fft.rfftfreq(rate, 1 / rate) > rate * 0.35] = 0
        signal = np.fft.irfft(spectrum, n=rate)
    else:
        signal = dynamic_audio(rate)[:, 0]
    audio = np.column_stack((signal, signal * 0.8)).astype(np.float32)
    path = tmp_path / "reference.wav"
    _write_wav(path, audio, rate, "float32")
    measured = measure_true_peak(audio, rate)
    _, peak = reference(ffmpeg, path)
    assert measured["true_peak_dbtp"] == pytest.approx(peak, abs=0.2)
    if kind == "intersample":
        assert measured["true_peak"] > np.max(np.abs(audio)) * 1.3


def test_compressor_transfer_knee_makeup_and_stereo_link():
    rate = 22050
    audio = np.tile([0.5, 0.125], (rate, 1)).astype(np.float32)
    settings = BusCompressor(threshold_dbfs=-18, ratio=4, knee_db=0)
    output, report = _compress(audio, rate, settings)
    reduction = (20 * np.log10(0.5) + 18) * 0.75
    assert report["max_gain_reduction_db"] == pytest.approx(reduction, abs=0.001)
    assert output[-1, 0] / output[-1, 1] == pytest.approx(4)
    assert output[0, 0] > output[rate // 2, 0]
    knee_audio = np.full((rate, 2), 10 ** (-18 / 20), dtype=np.float32)
    hard, _ = _compress(knee_audio, rate, settings)
    soft, _ = _compress(knee_audio, rate, settings.model_copy(update={"knee_db": 6}))
    assert soft[-1, 0] < hard[-1, 0]
    bypass, _ = _compress(audio, rate, BusCompressor(ratio=1))
    np.testing.assert_array_equal(bypass, audio)
    makeup, _ = _compress(audio, rate, BusCompressor(ratio=1, makeup_db=6))
    np.testing.assert_allclose(makeup, audio * 10**0.3)


def test_compressor_release_and_attack_controls():
    rate = 22050
    audio = np.full((rate, 2), 0.5, dtype=np.float32)
    audio[rate // 2 :] = 0.02
    fast, _ = _compress(audio, rate, BusCompressor(attack_seconds=0.001, release_seconds=0.01))
    slow, _ = _compress(audio, rate, BusCompressor(attack_seconds=0.1, release_seconds=1))
    assert fast[100, 0] < slow[100, 0]
    assert fast[-1, 0] > slow[-1, 0]


def test_sliding_detector_matches_brute_force():
    values = np.random.default_rng(7).uniform(0, 1, 173)
    for size in (1, 2, 13, 173, 400):
        expected = [min(values[i : i + size]) for i in range(len(values))]
        np.testing.assert_array_equal(_future_min(values, size), expected)


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
@pytest.mark.parametrize("factor", [4, 8])
def test_limiter_ceiling_link_alignment_and_boundaries(rate, factor, tmp_path, ffmpeg):
    audio = dynamic_audio(rate) * 8
    audio[0] = [1, 0.7]
    audio[-1] = [-1, -0.7]
    output, report = _limit(audio, rate, TruePeakLimiter(oversample=factor))
    assert len(output) == len(audio)
    assert np.isfinite(output).all()
    assert measure_true_peak(output, rate, oversample=8)["true_peak_dbtp"] <= -1
    np.testing.assert_allclose(output[:, 1], output[:, 0] * 0.7, atol=2e-6)
    assert report["max_gain_reduction_db"] > 10
    _write_wav(tmp_path / "limited.wav", output, rate, "pcm24")
    assert reference(ffmpeg, tmp_path / "limited.wav")[1] <= -1
    impulse = np.zeros((rate, 2), dtype=np.float32)
    impulse[rate // 2] = 10
    limited, _ = _limit(impulse, rate, TruePeakLimiter())
    assert np.argmax(np.abs(limited[:, 0])) == rate // 2


@pytest.mark.parametrize("format", ["pcm16", "pcm24", "float32"])
def test_target_dynamic_mix_with_ffmpeg(format, tmp_path, ffmpeg):
    pytest.importorskip("pyloudnorm")
    rate = 44100
    audio = dynamic_audio(rate)
    settings = Mastering(compressor=BusCompressor(), limiter=TruePeakLimiter(), target_lufs=-14)
    output, _, report, loudness = process_master(
        audio, rate, settings, -14, -1, _RenderControl(None, None), True
    )
    assert report["limiter"]["max_gain_reduction_db"] > 1
    assert loudness["integrated_lufs"] == pytest.approx(-14, abs=0.1)
    path = tmp_path / "master.wav"
    _write_wav(path, output, rate, format)
    lufs, peak = reference(ffmpeg, path)
    assert lufs == pytest.approx(-14, abs=0.2)
    assert peak <= -1


def test_score_cli_preview_stems_and_target_override(tmp_path, capsys):
    pytest.importorskip("pyloudnorm")
    score = Song(
        sample_rate=22050,
        beats=2,
        tracks=[Track(name="Tone", instrument="sine", notes=[Note(pitch="A4", duration=2)])],
        mastering=Mastering(limiter=TruePeakLimiter(), target_lufs=-14),
    )
    source = tmp_path / "score with spaces.json"
    score.save(source)
    result = render_audio(score)
    assert result.report["loudness"]["target_reached"]
    preview = render_preview_audio(score, start_seconds=0.2, duration_seconds=0.3)
    np.testing.assert_array_equal(preview.audio, result.audio[4410:11025])
    assert (
        main(
            [
                "render",
                str(source),
                "-o",
                str(tmp_path / "mix.wav"),
                "--target-lufs",
                "-18",
                "--stems",
                str(tmp_path / "stems"),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["loudness"]["achieved_lufs"] == pytest.approx(-18, abs=0.1)
    assert "omit master effects and dynamics" in str(report["warnings"])
    assert (
        main(
            [
                "render",
                str(source),
                "-o",
                str(tmp_path / "mix.wav"),
                "--target-lufs",
                "-14",
                "--peak-ceiling-dbfs",
                "-1",
            ]
        )
        == 2
    )
    assert "conflicts" in capsys.readouterr().err


def test_unreachable_target_silence_and_preflight(tmp_path):
    pytest.importorskip("pyloudnorm")
    settings = Mastering(limiter=TruePeakLimiter(ceiling_dbtp=-20), target_lufs=-1)
    song = Song(
        sample_rate=22050,
        beats=1,
        mastering=settings,
        tracks=[Track(name="Tone", instrument="sine", notes=[Note()])],
    )
    result = render_audio(song)
    assert not result.report["loudness"]["target_reached"]
    assert result.report["true_peak"]["true_peak_dbtp"] <= -20
    silent = song.model_copy(update={"tracks": (Track(name="Rest"),)})
    report = render_audio(silent).report
    assert report["true_peak"]["true_peak_dbtp"] is None
    assert report["loudness"]["achieved_lufs"] is None
    json.dumps(report, allow_nan=False)
    path = tmp_path / "existing.wav"
    path.write_bytes(b"existing")
    with pytest.raises(ValueError, match="normalize=False"):
        render(song, path, normalize=False)
    assert path.read_bytes() == b"existing"


def test_invalid_meter_inputs():
    for audio in (np.zeros(0), np.zeros((4, 3)), np.array([np.nan]), np.zeros(4, dtype=int)):
        with pytest.raises(ValueError):
            measure_true_peak(audio, 44100)
    with pytest.raises(ValueError):
        measure_true_peak(np.zeros(4), 44100, oversample=True)


@pytest.mark.parametrize("ceiling", [-1, -20, -60])
def test_hard_cut_and_quiet_ceiling_encoded_reference(ceiling, tmp_path, ffmpeg):
    rate = 22050
    signal = 2 * np.sin(2 * np.pi * np.arange(rate) / 4 + np.pi / 4)
    audio = np.column_stack((signal, signal)).astype(np.float32)
    result, _ = _limit(audio, rate, TruePeakLimiter(ceiling_dbtp=ceiling))
    _write_wav(tmp_path / "cut.wav", result, rate, "pcm16")
    assert reference(ffmpeg, tmp_path / "cut.wav")[1] <= ceiling


def test_block_boundaries_do_not_change_meter_or_limiter(monkeypatch):
    import audio_as_code.mastering as dsp

    audio = dynamic_audio(22050)[:10000]
    a, _ = _limit(audio, 22050, TruePeakLimiter())
    peak = measure_true_peak(audio, 22050)["true_peak"]
    monkeypatch.setattr(dsp, "_BLOCK", 127)
    b, _ = _limit(audio, 22050, TruePeakLimiter())
    assert measure_true_peak(audio, 22050)["true_peak"] == pytest.approx(peak, abs=1e-12)
    np.testing.assert_allclose(a, b, atol=1e-7)


def test_mastering_file_cli_options_and_output_aliases(tmp_path, capsys):
    source = tmp_path / "score.json"
    config = tmp_path / "chain.json"
    dest = tmp_path / "mix.wav"
    Song(beats=1, tracks=[Track(name="Tone", instrument="sine", notes=[Note()])]).save(source)
    config.write_text('{"compressor":{"ratio":3}}', encoding="utf-8")
    args = [
        "render",
        str(source),
        "-o",
        str(dest),
        "--mastering",
        str(config),
        "--limiter-ceiling-dbtp",
        "-1",
    ]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mastering"]["settings"]["compressor"]["ratio"] == 3
    assert report["encoded_measurements"]["ceiling_met"]
    original = config.read_bytes()
    assert main(["render", str(source), "-o", str(config), "--mastering", str(config)]) == 2
    assert config.read_bytes() == original
    capsys.readouterr()


def test_core_mastering_needs_no_loudness_dependency():
    import sys

    code = """
import sys
from audio_as_code import Song, Track, Note, Mastering, TruePeakLimiter, render_audio
song = Song(beats=1, tracks=[Track(name="Tone", instrument="sine", notes=[Note()])])
render_audio(song, mastering=Mastering(limiter=TruePeakLimiter()))
assert "pyloudnorm" not in sys.modules
assert "scipy" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


def test_empty_chain_bypasses_score_mastering_without_changing_audio():
    song = Song(beats=1, tracks=[Track(name="Tone", instrument="sine", notes=[Note()])])
    mastered = song.model_copy(update={"mastering": Mastering(compressor=BusCompressor())})
    expected = render_audio(song).audio
    np.testing.assert_array_equal(render_audio(mastered, mastering=Mastering()).audio, expected)


def test_true_peak_cancellation_stops_between_blocks(monkeypatch):
    import importlib

    from audio_as_code import RenderCancelled

    module = importlib.import_module("audio_as_code.mastering")
    original = module._high_block
    calls = []

    def block(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_high_block", block)
    with pytest.raises(RenderCancelled):
        module.measure_true_peak(
            np.zeros((100000, 2), dtype=np.float32), 44100, cancel=lambda: bool(calls)
        )
    assert len(calls) == 1


@pytest.mark.parametrize("stage", ["compressor", "limiter"])
def test_mastering_checks_cancellation_during_processing(stage):
    from audio_as_code import RenderCancelled

    checks = 0

    def cancel():
        nonlocal checks
        checks += 1
        return checks == 4

    settings = Mastering(**{stage: BusCompressor() if stage == "compressor" else TruePeakLimiter()})
    with pytest.raises(RenderCancelled):
        process_master(
            np.ones((100000, 2), dtype=np.float32),
            44100,
            settings,
            None,
            None,
            _RenderControl(cancel=cancel),
            True,
        )
    assert checks == 4


def test_cancel_encoded_meter_preserves_existing_output(tmp_path, monkeypatch):
    import importlib

    from audio_as_code import RenderCancelled

    module = importlib.import_module("audio_as_code.render")
    measure = module.measure_exported
    started = False

    def encoded(*args, **kwargs):
        nonlocal started
        started = True
        return measure(*args, **kwargs)

    monkeypatch.setattr(module, "measure_exported", encoded)
    output = tmp_path / "mix.wav"
    output.write_bytes(b"existing")
    song = Song(
        beats=1,
        tracks=[Track(name="Tone", instrument="sine", notes=[Note()])],
        mastering=Mastering(compressor=BusCompressor()),
    )
    with pytest.raises(RenderCancelled):
        render(song, output, cancel=lambda: started)
    assert output.read_bytes() == b"existing"
    assert not list(tmp_path.glob(".aac-*"))
