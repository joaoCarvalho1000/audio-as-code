import hashlib
import json
import math

import mido
import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import (
    Automation,
    Delay,
    Note,
    Reverb,
    Song,
    Track,
    export_midi,
    midi_pitch,
    render,
    render_audio,
)
from audio_as_code.automation import automation_values
from audio_as_code.cli import main
from audio_as_code.demo import demo_song
from audio_as_code.effects import apply_effects
from audio_as_code.render import _voice


def score(**kwargs):
    return Song(
        **{
            "beats": 4,
            "sample_rate": 22050,
            "tracks": [Track(name="Tone", instrument="sine", notes=[Note(duration=4)])],
            **kwargs,
        }
    )


def lane(parameter, *points, interpolation="linear"):
    return Automation(
        parameter=parameter,
        points=[{"beat": b, "value": v} for b, v in points],
        interpolation=interpolation,
    )


@pytest.mark.parametrize("interpolation", ["linear", "step"])
@pytest.mark.parametrize("start", [0, 65536])
def test_dense_tempo_automation_preserves_exact_reference(interpolation, start):
    song = score(
        beats=8,
        tempo_map=[{"beat": i / 128, "bpm": 60 + i % 241} for i in range(1024)],
    )
    automation = lane("pan", (0.125, -0.75), (2.25, 0.8), (7.75, -0.2), interpolation=interpolation)
    beats = np.array([point.beat for point in automation.points])
    values = np.array([point.value for point in automation.points])
    times = np.arange(start, start + 65536, dtype=np.float64) / song.sample_rate
    if interpolation == "step":
        point_times = [song.beat_to_seconds(beat) for beat in beats]
        indices = np.searchsorted(point_times, times, side="right") - 1
        expected = values[np.maximum(indices, 0)]
    else:
        knots = np.unique(np.concatenate((beats, [change.beat for change in song.tempo_map])))
        expected = np.interp(
            times, [song.beat_to_seconds(beat) for beat in knots], np.interp(knots, beats, values)
        )
    np.testing.assert_array_equal(
        automation_values(song, automation, start, start + 65536), expected
    )


def test_legacy_audio_and_score_hash_are_unchanged():
    song = demo_song()
    result = render_audio(song)
    # Original mixing algorithm as a local oracle, avoiding a platform-specific
    # floating-point hash (FFT/trigonometric libraries can differ across platforms).
    expected = np.zeros((round(song.seconds * song.sample_rate), 2), np.float32)
    for track in song.tracks:
        stem = np.zeros_like(expected)
        angle = (track.pan + 1) * np.pi / 4
        for index, note in enumerate(track.notes):
            start = round(note.start * (song.sample_rate * 60 / song.bpm))
            end = round((note.start + note.duration) * (song.sample_rate * 60 / song.bpm))
            seed = int.from_bytes(
                hashlib.sha256(f"{song.seed}:{track.name}:{index}".encode()).digest()[:8], "little"
            )
            voice = _voice(
                track.instrument,
                midi_pitch(note.pitch),
                end - start,
                song.sample_rate,
                seed,
                note.velocity,
                track.tone,
            )
            voice *= note.velocity * track.gain * song.master_gain
            stem[start:end, 0] += voice * math.cos(angle)
            stem[start:end, 1] += voice * math.sin(angle)
        expected += stem
    expected *= min(1, 0.95 / float(np.max(np.abs(expected))))
    np.testing.assert_array_equal(result.audio, expected)
    assert result.report["score_sha256"] == (
        "7e334d6897f6a7847ff1fee1810cde6fcd24a462deb9f6edb9c4e3e9563b0b81"
    )


def test_zero_mix_effects_are_exact_bypass_without_extra_tail():
    song = score()
    track = song.tracks[0].model_copy(update={"effects": (Delay(mix=0), Reverb(mix=0))})
    bypass = song.model_copy(update={"tracks": (track,), "effects": (Reverb(mix=0),)})
    assert bypass.render_seconds == song.seconds
    np.testing.assert_array_equal(render_audio(song).audio, render_audio(bypass).audio)


def test_tempo_integrates_note_start_end_and_midi(tmp_path):
    song = score(
        tempo_map=[{"beat": 2, "bpm": 60}],
        tracks=[Track(name="Crossing", instrument="sine", notes=[Note(start=1, duration=2)])],
    )
    assert song.beat_to_seconds(1) == 0.5
    assert song.beat_to_seconds(3) == 2
    assert song.seconds == 3
    audio = render_audio(song).audio
    assert len(audio) == 3 * song.sample_rate
    assert not np.any(audio[:11025])
    assert np.max(np.abs(audio[33075:44000])) > 0.1
    assert not np.any(audio[44100:])
    export_midi(song, tmp_path / "tempo.mid")
    midi = mido.MidiFile(tmp_path / "tempo.mid")
    assert midi.length == pytest.approx(song.seconds)
    tempos = [event for event in midi.tracks[0] if event.type == "set_tempo"]
    assert [(event.time, event.tempo) for event in tempos] == [(0, 500000), (960, 1000000)]


def test_zero_tempo_change_overrides_base_and_multiple_segments():
    song = score(
        tempo_map=[{"beat": 0, "bpm": 60}, {"beat": 1, "bpm": 120}, {"beat": 3, "bpm": 240}]
    )
    assert song.seconds == 2.25
    assert song.beat_to_seconds(5) == 2.5


def test_linear_automation_follows_beats_across_tempo_and_holds_endpoints():
    song = score(tempo_map=[{"beat": 2, "bpm": 60}])
    control = lane("gain", (1, 0.2), (3, 0.8))
    for seconds, expected in [
        (0, 0.2),
        (0.5, 0.2),
        (0.75, 0.35),
        (1, 0.5),
        (1.5, 0.65),
        (2.5, 0.8),
        (4, 0.8),
    ]:
        start = round(seconds * song.sample_rate)
        assert automation_values(song, control, start, start + 1)[0] == pytest.approx(
            expected, abs=2e-5
        )


def test_step_automation_changes_at_first_sample_on_or_after_point():
    song = score()
    control = lane("pan", (0, -1), (1, 1), interpolation="step")
    np.testing.assert_array_equal(automation_values(song, control, 11024, 11027), [-1, 1, 1])


def test_gain_pan_and_master_automation_are_audible_absolute_controls():
    track = Track(
        name="Move",
        instrument="sine",
        gain=0,
        pan=0,
        automation=[lane("gain", (0, 0.7)), lane("pan", (0, -1), (2, 1), interpolation="step")],
        notes=[Note(duration=4)],
    )
    song = score(master_gain=0, automation=[lane("master_gain", (0, 0.5))], tracks=[track])
    audio = render_audio(song).audio
    assert np.max(np.abs(audio[100:20000, 0])) > 0.1
    assert np.max(np.abs(audio[:22050, 1])) == 0
    assert np.max(np.abs(audio[22050:, 0])) < 1e-15
    assert np.max(np.abs(audio[22050:, 1])) > 0.1


def test_release_extends_last_note_and_note_override_disables_it():
    track = Track(name="Release", instrument="sine", release_seconds=0.5, notes=[Note(duration=4)])
    song = score(tracks=[track])
    result = render_audio(song)
    assert song.seconds == 2 and song.render_seconds == 2.5
    assert result.report["tail_seconds"] == 0.5
    assert np.max(np.abs(result.audio[44100:50000])) > 0.1
    assert np.all(result.audio[-1] == 0)
    override = track.model_copy(update={"notes": (Note(duration=4, release_seconds=0),)})
    assert score(tracks=[override]).render_seconds == 2


@pytest.mark.parametrize("instrument", ["guitar", "bell", "flute", "violin", "drum_machine"])
def test_release_supported_for_procedural_voice_families(instrument):
    song = score(
        beats=1,
        tracks=[
            Track(
                name="Voice",
                instrument=instrument,
                release_seconds=0.3,
                notes=[Note(pitch=36 if instrument == "drum_machine" else 60)],
            )
        ],
    )
    result = render_audio(song)
    assert np.isfinite(result.audio).all()
    assert result.report["audio"]["duration_seconds"] == 0.8
    assert np.all(result.audio[-1] == 0)


def test_delay_impulse_exact_repeats_and_feedback_zero():
    impulse = np.zeros((1000, 2), np.float32)
    impulse[0] = 1
    effect = Delay(time_seconds=0.1, feedback=0.5, repeats=3, mix=1)
    audio = apply_effects(impulse, (effect,), 1000)
    np.testing.assert_array_equal(audio[[100, 200, 300], 0], [1, 0.5, 0.25])
    assert np.count_nonzero(audio[:, 0]) == 3
    assert not np.any(audio[:100])
    song = score(effects=[Delay(time_seconds=0.1, feedback=0, repeats=16)])
    assert song.render_seconds == 2.1


def test_reverb_impulse_is_stereo_deterministic_finite_and_decays():
    rate = 22050
    impulse = np.zeros((rate * 3, 2), np.float32)
    impulse[0] = 1
    effects = (Reverb(decay_seconds=1, mix=1),)
    a = apply_effects(impulse, effects, rate)
    np.testing.assert_array_equal(a, apply_effects(impulse, effects, rate))
    assert np.isfinite(a).all() and np.max(np.abs(a)) < 1
    assert not np.array_equal(a[:, 0], a[:, 1])
    assert np.sum(a[: rate // 2] ** 2) > 100 * np.sum(a[rate : rate * 2] ** 2)
    assert np.max(np.abs(a[round(1.1 * rate) + 2 :])) < 1e-8


def test_effect_chains_tails_stems_and_clipping(tmp_path):
    track = Track(
        name="Echo",
        instrument="sine",
        gain=1,
        release_seconds=0.2,
        notes=[Note(duration=4, velocity=1)] * 8,
        effects=[Delay(time_seconds=0.1, repeats=2)],
    )
    song = score(master_gain=1, tracks=[track], effects=[Reverb(decay_seconds=0.5)])
    assert song.render_seconds == pytest.approx(3)
    report = render(song, tmp_path / "mix.wav", stems_dir=tmp_path / "stems")
    assert report["audio"]["peak"] <= 0.951
    assert report["gain_applied"] < 1
    assert report["audio"]["frames"] == report["stems"][0]["audio"]["frames"]
    assert any("omit master effects" in warning for warning in report["warnings"])
    clipped = render_audio(song, normalize=False)
    assert clipped.report["before_gain"]["clipped_samples"] > 0


def test_tail_limit_is_checked_before_writing(tmp_path):
    song = score(beats=598, effects=[Reverb(decay_seconds=2)], tracks=[Track(name="Rest")])
    assert song.seconds == 299
    with pytest.raises(ValueError, match="300 seconds"):
        render(song, tmp_path / "blocked.wav")
    assert not (tmp_path / "blocked.wav").exists()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tempo_map": [{"beat": 2, "bpm": 60}, {"beat": 1, "bpm": 80}]},
        {"tempo_map": [{"beat": 1, "bpm": 60}, {"beat": 1, "bpm": 80}]},
        {"tempo_map": [{"beat": 4, "bpm": 60}]},
        {"tempo_map": [{"beat": 0, "bpm": 0}]},
        {"automation": [{"parameter": "gain", "points": [{"beat": 0, "value": 1}]}]},
        {"automation": [{"parameter": "master_gain", "points": [{"beat": 5, "value": 1}]}]},
        {"effects": [{"type": "delay", "feedback": 1}]},
        {"effects": [{"type": "delay", "repeats": True}]},
        {"effects": [{"type": "delay", "time_seconds": float("nan")}]},
        {"effects": [{"type": "reverb", "decay_seconds": 6}]},
        {"effects": [{"type": "convolution", "path": "recording.wav"}]},
    ],
)
def test_invalid_controls_rejected(kwargs):
    with pytest.raises(ValidationError):
        score(**kwargs)


def test_invalid_lanes_releases_and_unchecked_copy():
    with pytest.raises(ValidationError):
        lane("gain", (0, -0.1))
    with pytest.raises(ValidationError):
        lane("pan", (1, -1), (1, 1))
    with pytest.raises(ValidationError):
        Track(name="Duplicate", automation=[lane("pan", (0, 0))] * 2)
    with pytest.raises(ValidationError):
        Note(release_seconds=11)
    song = score().model_copy(update={"effects": (Delay.model_construct(feedback=3),)})
    with pytest.raises(ValidationError):
        render_audio(song)


def test_expressive_cli_roundtrip_and_seed(tmp_path, capsys):
    song = score(
        tempo_map=[{"beat": 2, "bpm": 90}],
        effects=[Reverb()],
        tracks=[
            Track(
                name="Noise",
                instrument="snare",
                release_seconds=0.2,
                notes=[Note(start=3)],
                effects=[Delay()],
            )
        ],
    )
    a, b = render_audio(song), render_audio(song)
    np.testing.assert_array_equal(a.audio, b.audio)
    changed = render_audio(song.model_copy(update={"seed": 99}))
    assert not np.array_equal(a.audio, changed.audio)
    path = tmp_path / "score.json"
    song.save(path)
    assert Song.load(path) == song
    assert main(["validate", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["render_duration_seconds"] > result["duration_seconds"]
    assert main(["render", str(path), "-o", str(tmp_path / "song.wav")]) == 0
    assert json.loads(capsys.readouterr().out)["tail_seconds"] > 0
    midi = export_midi(song, tmp_path / "song.mid")
    assert "not exported" in midi["warnings"][0]
