"""Format, excerpt-context, cancellation and file-publication contracts."""

import importlib
import struct
import wave

import numpy as np
import pytest

from audio_as_code import Automation, Delay, Note, Reverb, Song, Track, analyze_wav, render
from audio_as_code._audio import _write_wav
from audio_as_code.demo import demo_song
from audio_as_code.render import (
    RenderCancelled,
    render_audio,
    render_preview,
    render_preview_audio,
)

render_module = importlib.import_module("audio_as_code.render")


def test_default_articulation_fields_preserve_first_light_score_identity():
    result = render_audio(demo_song())
    assert result.report["score_sha256"] == (
        "7e334d6897f6a7847ff1fee1810cde6fcd24a462deb9f6edb9c4e3e9563b0b81"
    )


def score():
    return Song(
        sample_rate=22050,
        beats=4,
        seed=731,
        tempo_map=[{"beat": 2, "bpm": 90}],
        effects=[Reverb(decay_seconds=0.2, mix=0.15)],
        tracks=[
            Track(
                name="Noise",
                instrument="snare",
                gain=1,
                release_seconds=0.1,
                automation=[
                    Automation(
                        parameter="pan",
                        points=[{"beat": 0, "value": -0.7}, {"beat": 4, "value": 0.6}],
                    )
                ],
                effects=[Delay(time_seconds=0.2, repeats=3, feedback=0.5)],
                notes=[Note(start=0, velocity=1)] * 12 + [Note(start=2), Note(start=3)],
            ),
            Track(name="Tone", instrument="sine", notes=[Note(duration=4)]),
        ],
    )


def float_wave(values, channels=2, rate=22050):
    values = np.asarray(values, dtype="<f4")
    data = values.tobytes()
    return (
        b"RIFF"
        + struct.pack("<I", 50 + len(data))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHHH", 18, 3, channels, rate, rate * channels * 4, channels * 4, 32, 0)
        + b"fact"
        + struct.pack("<II", 4, len(values) // channels)
        + b"data"
        + struct.pack("<I", len(data))
        + data
    )


@pytest.mark.parametrize("wav_format,width", [("pcm16", 2), ("pcm24", 3), ("float32", 4)])
def test_formats_roundtrip_known_samples_and_headers(tmp_path, wav_format, width):
    path = tmp_path / "known.wav"
    audio = np.array([[-1.5, -1], [-0.25, 0], [0.25, 1], [1.5, 1 / 8388608]], np.float32)
    _write_wav(path, audio, 22050, wav_format)
    data = path.read_bytes()
    assert struct.unpack_from("<I", data, 4)[0] == len(data) - 8
    assert struct.unpack_from("<H", data, 20)[0] == (3 if wav_format == "float32" else 1)
    assert struct.unpack_from("<H", data, 32)[0] == width * 2
    if wav_format == "float32":
        assert data == float_wave(audio.reshape(-1))
        decoded = np.frombuffer(data[58:], "<f4").reshape(-1, 2)
        np.testing.assert_array_equal(decoded, audio)
    else:
        with wave.open(str(path), "rb") as stream:
            assert stream.getsampwidth() == width
            raw = stream.readframes(len(audio))
        integers = np.array(
            [
                int.from_bytes(raw[i : i + width], "little", signed=True)
                for i in range(0, len(raw), width)
            ]
        )
        scale = 2 ** (width * 8 - 1)
        expected = np.clip(np.rint(audio.astype(np.float64) * scale), -scale, scale - 1)
        np.testing.assert_array_equal(integers.reshape(-1, 2), expected)
        decoded = integers.reshape(-1, 2).astype(np.float64) / scale
    report = analyze_wav(path)
    assert report["frames"] == len(audio)
    assert report["channels"] == 2
    assert report["rms"] == pytest.approx(np.sqrt(np.mean(decoded.astype(np.float64) ** 2)))
    assert report["peak"] == np.max(np.abs(decoded))
    assert report["full_scale_samples"] == 4
    assert report.get("wav_format", "pcm16") == wav_format


def test_pcm16_default_bytes_and_report_unchanged(tmp_path):
    song = score()
    result = render_audio(song)
    path = tmp_path / "default.wav"
    report = render(song, path)
    reference = tmp_path / "reference.wav"
    pcm = np.clip(np.rint(result.audio * 32768), -32768, 32767).astype("<i2")
    with wave.open(str(reference), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(song.sample_rate)
        stream.writeframes(pcm.tobytes())
    assert path.read_bytes() == reference.read_bytes()
    assert {key: report[key] for key in result.report} == result.report
    assert "wav_format" not in report and "wav_format" not in report["wav"]


@pytest.mark.parametrize("wav_format", ["pcm16", "pcm24", "float32"])
def test_stems_use_selected_format_and_float_preserves_overs(tmp_path, wav_format):
    song = Song(
        sample_rate=22050,
        beats=1,
        master_gain=1,
        tracks=[Track(name="Loud", instrument="sine", gain=1, notes=[Note(velocity=1)] * 10)],
    )
    report = render(
        song,
        tmp_path / "mix.wav",
        stems_dir=tmp_path / "stems",
        normalize=False,
        wav_format=wav_format,
    )
    stem = analyze_wav(tmp_path / "stems" / "01.wav")
    assert stem.get("wav_format", "pcm16") == wav_format
    assert report["wav"]["peak"] > 1 if wav_format == "float32" else report["wav"]["peak"] == 1
    assert stem["peak"] == report["wav"]["peak"]
    if wav_format == "float32":
        assert "was clipped" not in " ".join(report["warnings"])
        assert "hard-clip" not in " ".join(report["warnings"])


@pytest.mark.parametrize("normalize", [True, False])
@pytest.mark.parametrize("start,duration", [(0.73451, 0.63017), (2.85, 100)])
def test_preview_preserves_full_render_context(normalize, start, duration):
    song = score()
    full = render_audio(song, normalize=normalize)
    preview = render_preview_audio(
        song, start_seconds=start, duration_seconds=duration, normalize=normalize
    )
    first = round(start * song.sample_rate)
    last = round(min(song.render_seconds, start + duration) * song.sample_rate)
    np.testing.assert_array_equal(preview.audio, full.audio[first:last])
    assert preview.report["score_sha256"] == full.report["score_sha256"]
    assert preview.report["gain_applied"] == full.report["gain_applied"]
    assert preview.report["preview"]["context_audio"] == full.report["audio"]
    assert preview.report["audio"]["frames"] == last - first


@pytest.mark.parametrize("wav_format", ["pcm16", "pcm24", "float32"])
def test_preview_file_exactly_matches_encoding_full_render_crop(tmp_path, wav_format):
    song = score()
    first, last = 10000, 25000
    expected = render_audio(song).audio[first:last]
    path = tmp_path / "preview.wav"
    report = render_preview(
        song,
        path,
        start_seconds=first / song.sample_rate,
        duration_seconds=(last - first) / song.sample_rate,
        wav_format=wav_format,
    )
    reference = tmp_path / "reference.wav"
    _write_wav(reference, expected, song.sample_rate, wav_format)
    assert path.read_bytes() == reference.read_bytes()
    assert report["wav"] == analyze_wav(path)


@pytest.mark.parametrize(
    "start,duration",
    [
        (-1, 1),
        (0, 0),
        (0, -1),
        (4, 1),
        (float("nan"), 1),
        (0, float("inf")),
        (True, 1),
        (0, "1"),
        (0, 1e-20),
    ],
)
def test_invalid_preview_is_rejected_before_writes(tmp_path, start, duration):
    destination = tmp_path / "absent" / "preview.wav"
    with pytest.raises(ValueError):
        render_preview(score(), destination, start_seconds=start, duration_seconds=duration)
    assert not destination.parent.exists()


def test_preview_does_not_bypass_full_render_limit():
    song = Song(beats=1000, tracks=[Track(name="Long")])
    with pytest.raises(ValueError, match="300 seconds"):
        render_preview_audio(song, start_seconds=0, duration_seconds=1)


def test_progress_does_not_change_audio_and_cancellation_checks_between_notes():
    song = score()
    events = []
    full = render_audio(song)
    observed = render_audio(song, progress=events.append)
    np.testing.assert_array_equal(observed.audio, full.audio)
    assert observed.report == full.report
    assert events[0].phase == "tracks" and events[-1].phase == "analysis"
    assert all(0 <= event.completed <= event.total for event in events)
    cancel = False

    def on_progress(event):
        nonlocal cancel
        if event.phase == "notes" and event.completed == 1:
            cancel = True

    with pytest.raises(RenderCancelled, match="cancelled"):
        render_audio(song, progress=on_progress, cancel=lambda: cancel)


@pytest.mark.parametrize("failure", ["cancel", "callback", "encode"])
def test_failure_before_publication_preserves_all_destinations(tmp_path, monkeypatch, failure):
    song = score()
    paths = [tmp_path / "mix.wav", tmp_path / "01.wav", tmp_path / "02.wav"]
    for path in paths:
        path.write_bytes(b"existing " + path.name.encode())
    before = [path.read_bytes() for path in paths]
    cancelled = False

    def progress(event):
        nonlocal cancelled
        if event.phase == "export" and event.completed == event.total:
            if failure == "callback":
                raise RuntimeError("callback failed")
            cancelled = failure == "cancel"

    original = render_module._write_wav
    calls = 0

    def write(*args):
        nonlocal calls
        calls += 1
        if calls == 3 and failure == "encode":
            raise OSError("encoding failed")
        return original(*args)

    monkeypatch.setattr(render_module, "_write_wav", write)
    with pytest.raises((RenderCancelled, RuntimeError, OSError)):
        render(song, paths[0], stems_dir=tmp_path, progress=progress, cancel=lambda: cancelled)
    assert [path.read_bytes() for path in paths] == before
    assert not list(tmp_path.glob(".aac-*"))


@pytest.mark.parametrize("wav_format", ["pcm8", "PCM24", None])
def test_invalid_format_does_not_write(tmp_path, wav_format):
    with pytest.raises(ValueError, match="wav_format"):
        render(score(), tmp_path / "missing" / "mix.wav", wav_format=wav_format)
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_float_analysis_rejects_nonfinite_samples(tmp_path, value):
    path = tmp_path / "invalid.wav"
    path.write_bytes(float_wave([value, 0]))
    with pytest.raises(ValueError, match="non-finite"):
        analyze_wav(path)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda data: data[:-1], "truncated"),
        (lambda data: data[:32] + struct.pack("<H", 4) + data[34:], "alignment"),
        (lambda data: data[:24] + struct.pack("<I", 0) + data[28:], "sample rate"),
        (lambda data: data[:22] + struct.pack("<H", 0) + data[24:], "channel count"),
        (lambda data: data[:36] + struct.pack("<H", 2) + data[38:], "extension"),
    ],
)
def test_float_analysis_rejects_malformed_headers(tmp_path, mutation, match):
    path = tmp_path / "invalid.wav"
    path.write_bytes(mutation(float_wave([0.5, -0.5])))
    with pytest.raises((ValueError, wave.Error), match=match):
        analyze_wav(path)


def test_float_analysis_rejects_incomplete_frame(tmp_path):
    path = tmp_path / "invalid.wav"
    path.write_bytes(float_wave([0.5, -0.5, 0.25]))
    with pytest.raises(ValueError, match="incomplete float frame"):
        analyze_wav(path)


def test_float_analysis_empty_and_large_finite_samples(tmp_path):
    path = tmp_path / "empty.wav"
    path.write_bytes(float_wave([]))
    assert analyze_wav(path)["silent"]
    path.write_bytes(float_wave([np.finfo(np.float32).max] * 4))
    report = analyze_wav(path)
    assert np.isfinite(report["rms"]) and report["rms"] == report["peak"]


def test_pcm24_analysis_rejects_partial_frame(tmp_path):
    path = tmp_path / "partial.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(22050)
        stream.writeframes(b"\0" * 9)
    with pytest.raises(ValueError, match="incomplete PCM frame"):
        analyze_wav(path)
