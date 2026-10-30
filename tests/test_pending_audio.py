"""Behavioral checks for periodic tails, depth experiments and audition provenance."""

import json

import numpy as np
import pytest

from audio_as_code import Delay, LoopRegion, Note, Reverb, Song, TempoChange, Track
from audio_as_code.arrangement import render_loop_preview, render_periodic_loop
from audio_as_code.experimental_pedal import PedalDepth, render_pedal_depth
from audio_as_code.render import render_audio
from examples.listening_evaluation import generate


def loop_song(**changes):
    return Song(
        **{
            "beats": 2,
            "bpm": 120,
            "sample_rate": 22050,
            "tracks": [
                Track(
                    name="Source",
                    instrument="sine",
                    gain=0.1,
                    release_seconds=0.2,
                    notes=[Note(start=1, duration=1)],
                    effects=[Delay(time_seconds=0.17, repeats=3), Reverb(decay_seconds=0.3)],
                )
            ],
            **changes,
        }
    )


def test_periodic_tail_matches_continuous_linear_context():
    song = loop_song()
    result = render_periodic_loop(song, LoopRegion(0, 2))
    frames = result.report["loop"]["cycle_frames"]
    assert frames == 22050
    assert len(result.audio) == frames * 2
    assert np.array_equal(result.audio[:frames], result.audio[frames:])
    assert result.report["loop"]["tail_frames_folded"] > 0
    # Independent oracle: render six actual cycles through one continuous effect
    # buffer, then inspect the sixth after the finite response has settled.
    track = song.tracks[0]
    continuous = Song.model_validate(
        {
            **song.model_dump(),
            "beats": 12,
            "tracks": [
                {
                    **track.model_dump(),
                    "notes": [
                        {**track.notes[0].model_dump(), "start": 1 + cycle * 2}
                        for cycle in range(6)
                    ],
                }
            ],
        }
    )
    expected = render_audio(continuous, normalize=False).audio[5 * frames : 6 * frames]
    np.testing.assert_allclose(result.audio[:frames], expected, atol=2e-7)
    assert np.array_equal(result.audio, render_periodic_loop(song, LoopRegion(0, 2)).audio)


def test_periodic_subregion_tempo_map_and_original_unchanged():
    song = loop_song(beats=5, tempo_map=[TempoChange(beat=2, bpm=90), TempoChange(beat=3, bpm=140)])
    before = song.model_dump_json()
    result = render_periodic_loop(song, LoopRegion(1, 4))
    report = result.report["loop"]
    assert report["cycle_frames"] == (
        round(song.beat_to_seconds(4) * song.sample_rate)
        - round(song.beat_to_seconds(1) * song.sample_rate)
    )
    assert len(result.audio) == 2 * report["cycle_frames"]
    assert song.model_dump_json() == before


def test_dry_loop_regression_and_bounds():
    song = Song(beats=2, sample_rate=22050, tracks=[Track(name="Dry", notes=[Note(duration=0.5)])])
    old = render_loop_preview(song, LoopRegion(0, 2))
    new = render_periodic_loop(song, LoopRegion(0, 2))
    assert np.array_equal(old.audio, new.audio)
    with pytest.raises(ValueError, match="within"):
        render_periodic_loop(song, LoopRegion(0, 3))
    with pytest.raises(ValueError, match="crosses"):
        render_periodic_loop(song, LoopRegion(0.25, 2))
    with pytest.raises(ValueError, match="32-cycle"):
        render_periodic_loop(loop_song(), LoopRegion(0, 0.001))


def test_periodic_rejects_unsupported_processing():
    from audio_as_code import Distortion, PedalEvent

    with pytest.raises(ValueError, match="only generated"):
        render_periodic_loop(loop_song(effects=[Distortion()]), LoopRegion(0, 2))
    song = Song(
        beats=2,
        tracks=[Track(name="Piano", instrument="piano", pedal=[PedalEvent(beat=0, down=True)])],
    )
    with pytest.raises(ValueError, match="pedal"):
        render_periodic_loop(song, LoopRegion(0, 2))


def piano_song():
    return Song(
        beats=4,
        sample_rate=22050,
        tracks=[
            Track(
                name="Piano",
                instrument="piano",
                gain=0.2,
                notes=[Note(pitch=69, duration=0.5), Note(pitch=69, start=1, duration=0.5)],
            )
        ],
    )


def test_depth_damping_is_between_lifted_and_held_without_restoring_energy():
    song = piano_song()
    before = render_audio(song)
    results = [render_pedal_depth(song, (PedalDepth(0, depth),)) for depth in (0, 0.5, 1)]
    assert np.array_equal(render_pedal_depth(song, ()).audio, results[0].audio)
    energies = [
        float(np.sum(result.audio[round(0.85 * song.sample_rate) :] ** 2)) for result in results
    ]
    assert 0 < energies[0] < energies[1] < energies[2]
    for result in results:
        assert np.all(np.isfinite(result.audio))
        assert np.max(np.abs(result.audio)) < 1
        assert len(result.audio) == round((song.seconds + 0.25) * song.sample_rate)
        assert np.max(np.abs(result.audio[-1])) == 0
        # A4 fundamental is retained during the key-held interval.
        data = result.audio[1000:5000, 0]
        spectrum = np.abs(np.fft.rfft(data * np.hanning(len(data)), n=65536))
        frequency = np.argmax(spectrum) * song.sample_rate / 65536
        assert frequency == pytest.approx(440, abs=3)
    recapture = render_pedal_depth(song, (PedalDepth(0, 0), PedalDepth(1.7, 1)))
    tail = slice(round(1.0 * song.sample_rate), None)
    # The second key releases at .75s; the later press at .85s cannot
    # recover its exp(-60*.1) amplitude loss (squared for energy).
    assert np.sum(recapture.audio[tail] ** 2) < np.sum(results[2].audio[tail] ** 2) * 1e-4
    assert np.array_equal(before.audio, render_audio(song).audio)
    assert before.report["score_sha256"] == render_audio(song).report["score_sha256"]


@pytest.mark.parametrize(
    "events",
    [
        (PedalDepth(2, 0.5), PedalDepth(1, 0)),
        (PedalDepth(5, 1),),
    ],
)
def test_depth_rejects_invalid_timeline(events):
    with pytest.raises(ValueError):
        render_pedal_depth(piano_song(), events)


@pytest.mark.parametrize("depth", [-0.1, 1.1, True, float("nan")])
def test_depth_range(depth):
    with pytest.raises(ValueError):
        PedalDepth(0, depth)


def test_audition_reproducibility_and_baseline_preservation(tmp_path, monkeypatch):
    # Keep the test focused; the command renders the entire five-family set.
    monkeypatch.setattr("examples.listening_evaluation.VOICES", ("piano",))
    baseline = tmp_path / "baseline"
    first = generate(baseline)
    preserved = (baseline / "manifest.json").read_bytes()
    second = generate(tmp_path / "candidate", baseline)
    assert all(c["same_wav"] and c["same_score"] for c in second["baseline_comparison"].values())
    assert first["listening"]["piano-dry"]["status"] == "not_listened"
    assert json.loads(preserved)["clips"]["piano-dry"]["measurements"]["silent"] is False
    assert (baseline / "manifest.json").read_bytes() == preserved
    with pytest.raises((ValueError, FileExistsError)):
        generate(baseline, baseline)
