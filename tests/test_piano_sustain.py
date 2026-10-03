import hashlib
import importlib
import json

import mido
import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import (
    Delay,
    Note,
    PedalEvent,
    Song,
    Track,
    export_midi,
    inspect_score,
    render,
    render_audio,
)
from audio_as_code.render import _canonical_score, _voice


def piano(*, notes=None, pedal=None, beats=4, **kwargs):
    return Song(
        beats=beats,
        sample_rate=22050,
        tracks=[
            Track(
                name="Piano",
                instrument="piano",
                notes=notes if notes is not None else [Note(duration=0.5)],
                pedal=pedal if pedal is not None else [PedalEvent(beat=0, down=True)],
                **kwargs,
            )
        ],
    )


@pytest.mark.parametrize(
    "events",
    [
        [{"beat": 0, "down": 1}],
        [{"beat": 0, "down": "true"}],
        [{"beat": True, "down": True}],
        [{"beat": -1, "down": True}],
        [{"beat": float("nan"), "down": True}],
        [{"beat": 0, "down": False}],
        [{"beat": 0, "down": True}, {"beat": 1, "down": True}],
        [{"beat": 1, "down": True}, {"beat": 1, "down": False}],
        [{"beat": 1, "down": True}, {"beat": 0, "down": False}],
        [{"beat": 5, "down": True}],
        [{"beat": i / 1000, "down": i % 2 == 0} for i in range(1025)],
    ],
)
def test_invalid_pedal_events_are_rejected(events):
    with pytest.raises(ValidationError):
        piano(pedal=events)


@pytest.mark.parametrize("instrument", ["pluck", "electric_piano", "harpsichord", "drum_machine"])
def test_pedal_rejects_unsupported_instruments(instrument):
    with pytest.raises(ValidationError, match="only by piano"):
        Track(name="Unsupported", instrument=instrument, pedal=[PedalEvent(beat=0, down=True)])


def test_pedal_boundaries_apply_before_note_off_and_key_holds_survive_lift():
    notes = [Note(duration=end) for end in (0.5, 1, 1.5, 2, 2.5, 3, 3.5)]
    song = piano(
        notes=notes,
        pedal=[
            PedalEvent(beat=1, down=True),
            PedalEvent(beat=2, down=False),
            PedalEvent(beat=3, down=True),
        ],
    )
    track = song.tracks[0]
    assert [song.note_gate_end(track, note) for note in notes] == [0.5, 2, 2, 2, 2.5, 4, 4]
    assert [song.note_release_seconds(track, note) for note in notes] == [
        0,
        0.12,
        0.12,
        0,
        0,
        0.12,
        0.12,
    ]


@pytest.mark.parametrize("release,expected", [(None, 0.12), (0, 0), (0.3, 0.3)])
def test_note_release_overrides_default_damper_tail(release, expected):
    song = piano(notes=[Note(duration=0.5, release_seconds=release)])
    assert song.render_seconds == pytest.approx(2 + expected)
    audio = render_audio(song).audio
    assert not np.any(audio[-1])
    assert np.isfinite(audio).all()


def test_track_release_and_tempo_map_effect_tail_are_included():
    song = piano(release_seconds=0.25, effects=[Delay(time_seconds=0.1, repeats=2)])
    song = Song.model_validate({**song.model_dump(), "tempo_map": [{"beat": 1, "bpm": 60}]})
    assert song.seconds == 3.5
    assert song.render_seconds == pytest.approx(3.95)
    report = inspect_score(song)
    assert report["tracks"][0]["dry_end_seconds"] == 3.75
    assert report["tracks"][0]["effect_end_seconds"] == pytest.approx(3.95)
    assert report["tracks"][0]["pedal_auto_lift"]
    assert report["tracks"][0]["pedal_sustained_note_count"] == 1
    assert report["summary"]["max_note_polyphony"] == 1
    result = render_audio(song)
    assert len(result.audio) == round(3.95 * song.sample_rate)
    assert result.report["audio"]["clipped_samples"] == 0
    assert np.all(result.audio[-1] == 0)


def test_sustain_continues_after_key_release_and_damps_after_lift():
    events = [PedalEvent(beat=0, down=True), PedalEvent(beat=2, down=False)]
    wet = piano(pedal=events)
    dry = piano(pedal=[])
    wet_audio = render_audio(wet).audio
    dry_audio = render_audio(dry).audio
    rate = wet.sample_rate
    assert not np.any(dry_audio[round(0.3 * rate) :])
    assert np.max(np.abs(wet_audio[round(0.3 * rate) : rate])) > 0.005
    assert np.max(np.abs(wet_audio[rate : round(1.1 * rate)])) > 0
    assert not np.any(wet_audio[round(1.12 * rate) :])
    np.testing.assert_array_equal(wet_audio, render_audio(wet).audio)


def test_retrigger_keeps_independent_sustained_tails():
    song = piano(notes=[Note(duration=0.5), Note(start=1, duration=0.5)])
    track = song.tracks[0]
    actual = render_audio(song, normalize=False).audio
    rate = song.sample_rate
    expected = np.zeros(len(actual), dtype=np.float32)
    for index, note in enumerate(track.notes):
        start = round(note.start * rate / 2)
        held_end = round(2 * rate)
        end = held_end + round(0.12 * rate)
        seed = int.from_bytes(
            hashlib.sha256(f"{song.seed}:{track.name}:{index}".encode()).digest()[:8], "little"
        )
        voice = _voice(
            "piano", 60, end - start, rate, seed, note.velocity, held_frames=held_end - start
        )
        expected[start:end] += voice * note.velocity
    expected *= track.gain * np.cos(np.pi / 4)
    expected *= song.master_gain
    np.testing.assert_allclose(actual[:, 0], expected, rtol=3e-7, atol=1e-10)


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_pedal_audio_is_finite_bounded_and_ends_at_zero_at_supported_rates(rate):
    song = piano(notes=[Note(pitch="A4", duration=0.1, velocity=1)] * 20)
    song = Song.model_validate({**song.model_dump(), "sample_rate": rate, "master_gain": 1})
    result = render_audio(song)
    assert np.isfinite(result.audio).all()
    assert result.report["audio"]["clipped_samples"] == 0
    assert result.report["audio"]["peak"] <= 0.951
    assert not np.any(result.audio[[0, -1]])
    # Measure the surviving fundamental after key release, when only pedal holds it.
    signal = result.audio[round(0.2 * rate) : round(1.2 * rate), 0]
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal)), n=rate * 4))
    frequencies = np.fft.rfftfreq(rate * 4, 1 / rate)
    band = (frequencies > 425) & (frequencies < 455)
    measured = frequencies[band][np.argmax(spectrum[band])]
    assert abs(1200 * np.log2(measured / 440)) < 10


def test_held_pedal_tail_can_exceed_render_limit_before_any_write(tmp_path):
    song = piano(beats=600)
    assert song.render_seconds == 300.12
    assert not inspect_score(song)["readiness"]["render"]["ready"]
    with pytest.raises(ValueError, match="300 seconds"):
        render(song, tmp_path / "must-not-exist.wav")
    assert not (tmp_path / "must-not-exist.wav").exists()


def test_inspection_is_static_and_warns_about_pedal_tick_rounding(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("static inspection must not synthesize")

    monkeypatch.setattr(importlib.import_module("audio_as_code.render"), "render_audio", unexpected)
    song = piano(pedal=[PedalEvent(beat=0.0001, down=True), PedalEvent(beat=0.0002, down=False)])
    report = inspect_score(song)
    assert report["readiness"]["midi"]["ready"]
    codes = {issue["code"] for issue in report["issues"]}
    assert {"midi_pedal_receiver_behavior", "midi_pedal_timing_quantized"} <= codes


def test_midi_cc64_precedes_note_off_and_retrigger_and_auto_lifts(tmp_path):
    song = piano(
        notes=[Note(duration=1), Note(start=1, duration=1)],
        pedal=[PedalEvent(beat=1, down=True)],
    )
    path = tmp_path / "pedal.mid"
    report = export_midi(song, path)
    midi = mido.MidiFile(path)
    tick, events = 0, []
    for event in midi.tracks[1]:
        tick += event.time
        if event.type in {"note_off", "note_on"} or (
            event.type == "control_change" and event.control == 64
        ):
            events.append((tick, event.type, getattr(event, "value", None)))
    assert events == [
        (0, "note_on", None),
        (480, "control_change", 127),
        (480, "note_off", None),
        (480, "note_on", None),
        (960, "note_off", None),
        (1920, "control_change", 0),
    ]
    assert "CC64" in report["warnings"][0]
    assert midi.length == song.seconds


def test_empty_pedal_defaults_preserve_hash_audio_and_midi(tmp_path):
    explicit = piano(pedal=[])
    data = explicit.model_dump(mode="json")
    del data["tracks"][0]["pedal"]
    omitted = Song.model_validate(data)
    np.testing.assert_array_equal(render_audio(explicit).audio, render_audio(omitted).audio)
    assert "pedal" not in _canonical_score(explicit)["tracks"][0]
    assert (
        render_audio(explicit).report["score_sha256"]
        == render_audio(omitted).report["score_sha256"]
    )
    a, b = tmp_path / "a.mid", tmp_path / "b.mid"
    export_midi(explicit, a)
    export_midi(omitted, b)
    assert a.read_bytes() == b.read_bytes()
    assert "pedal" in json.loads(explicit.model_dump_json())["tracks"][0]


def test_unchecked_pedal_copy_is_revalidated_before_render_or_midi(tmp_path):
    valid = piano()
    invalid_track = valid.tracks[0].model_copy(update={"instrument": "pluck"})
    invalid = valid.model_copy(update={"tracks": (invalid_track,)})
    with pytest.raises(ValidationError, match="only by piano"):
        render_audio(invalid)
    with pytest.raises(ValidationError, match="only by piano"):
        export_midi(invalid, tmp_path / "invalid.mid")
