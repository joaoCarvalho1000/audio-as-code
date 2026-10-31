"""Behavioral checks for periodic tails, depth experiments and audition provenance."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from audio_as_code import Delay, LoopRegion, Note, Reverb, Song, TempoChange, Track
from audio_as_code.arrangement import render_loop_preview, render_periodic_loop
from audio_as_code.experimental_pedal import PedalDepth, render_pedal_depth
from audio_as_code.render import render_audio
from examples import listening_evaluation
from examples.listening_evaluation import generate, git_provenance


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


def test_depth_sample_ordering_key_release_and_song_end():
    song = piano_song()
    # Events at the release sample apply immediately. Pressing earlier while
    # the key is held has the same result, with no discontinuity at key-off.
    at_off = render_pedal_depth(song, (PedalDepth(0.5, 1),))
    earlier = render_pedal_depth(song, (PedalDepth(0, 1),))
    np.testing.assert_array_equal(at_off.audio, earlier.audio)
    # Song-end auto lift wins over an explicit final held event.
    at_end = render_pedal_depth(song, (PedalDepth(0, 1), PedalDepth(song.beats, 0.5)))
    np.testing.assert_array_equal(at_end.audio, earlier.audio)
    # Distinct beats may round to the same sample; the last depth wins.
    collapsed = render_pedal_depth(song, (PedalDepth(0, 0.2), PedalDepth(1e-8, 1)))
    np.testing.assert_array_equal(collapsed.audio, earlier.audio)
    # The first held interval and a repeated attack are unaffected by depth.
    lifted = render_pedal_depth(song, ())
    np.testing.assert_array_equal(lifted.audio[:5512], earlier.audio[:5512])


def test_depth_tempo_mapping_and_repeated_voice_superposition():
    song = piano_song().model_copy(update={"tempo_map": (TempoChange(beat=1, bpm=90),)})
    result = render_pedal_depth(song, (PedalDepth(0, 1), PedalDepth(1.5, 0.5)))
    assert len(result.audio) == round(song.seconds * song.sample_rate) + round(
        0.25 * song.sample_rate
    )
    from audio_as_code._voices import _voice
    from audio_as_code.render import _note_seed

    track = song.tracks[0]
    # During both keys' held/sustained interval at beat 1..1.5, their sum
    # must retain the first note, rather than replacing it on the repeat.
    start = round(song.beat_to_seconds(1) * song.sample_rate)
    stop = round(song.beat_to_seconds(1.5) * song.sample_rate)
    expected = np.zeros(stop - start, dtype=np.float32)
    for index, note in enumerate(track.notes):
        onset = round(song.beat_to_seconds(note.start) * song.sample_rate)
        voice = _voice(
            "piano",
            69,
            len(result.audio) - onset,
            song.sample_rate,
            _note_seed(song.seed, track.name, index),
            note.velocity,
            track.tone,
            held_frames=round(song.seconds * song.sample_rate) - onset,
        )
        expected += voice[start - onset : stop - onset] * note.velocity
    np.testing.assert_allclose(
        result.audio[start:stop, 0],
        expected * np.cos(np.pi / 4) * track.gain * song.master_gain,
        atol=1e-8,
    )


def test_depth_bounds_reject_before_synthesis(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("over-budget experiment reached synthesis")

    monkeypatch.setattr("audio_as_code.experimental_pedal._voice", unexpected)
    track = piano_song().tracks[0]
    for song, message in (
        (piano_song().model_copy(update={"beats": 600}), "300 seconds"),
        (
            piano_song().model_copy(
                update={"tracks": (track.model_copy(update={"notes": (track.notes[0],) * 4097}),)}
            ),
            "4096 notes",
        ),
        (
            piano_song().model_copy(
                update={
                    "beats": 100,
                    "tracks": (track.model_copy(update={"notes": (track.notes[0],) * 20}),),
                }
            ),
            "voice frames",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            render_pedal_depth(song, ())


def test_depth_pack_reports_measured_reproducible_comparison(tmp_path):
    from examples.pending_audio_experiments import generate

    generate(tmp_path / "first")
    generate(tmp_path / "second")
    first = json.loads((tmp_path / "first/report.json").read_text())
    second = json.loads((tmp_path / "second/report.json").read_text())
    assert first == second
    assert first["depth_comparison"]["ordered_release_energy"]
    for name in ("lifted", "half", "held"):
        report = first[f"depth-{name}"]
        assert report["finite"]
        assert report["audio"]["clipped_samples"] == 0
        assert report["audio"]["frames"] == 49612
        assert all(abs(t["local_peak_cents"]) < 15 for t in report["comparison"]["tuning"])
        assert (tmp_path / f"first/depth-{name}.wav").read_bytes() == (
            tmp_path / f"second/depth-{name}.wav"
        ).read_bytes()
    assert first["listening"]["status"] == "not_listened"


def test_review_pack_script_imports_shared_measurement_helper(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "examples/audio_review_pack.py"), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "output" in result.stdout


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


@pytest.mark.parametrize("foreign_parent", [False, True])
def test_archive_audition_keeps_hashes_without_borrowing_git(tmp_path, monkeypatch, foreign_parent):
    if foreign_parent:
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.test",
                "commit",
                "--allow-empty",
                "-m",
                "foreign checkout",
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
    root = Path(listening_evaluation.__file__).resolve().parents[1]
    archive = tmp_path / "extracted source"
    (archive / "examples").mkdir(parents=True)
    shutil.copytree(root / "src/audio_as_code", archive / "src/audio_as_code")
    shutil.copy2(root / "uv.lock", archive / "uv.lock")
    script = archive / "examples/listening_evaluation.py"
    shutil.copy2(listening_evaluation.__file__, script)
    monkeypatch.setattr(listening_evaluation, "__file__", str(script))
    monkeypatch.setattr(listening_evaluation, "VOICES", ("piano",))
    manifest = generate(tmp_path / "audition")
    assert manifest["source_commit"] is None
    assert manifest["source_dirty"] is None
    for field in ("lock_sha256", "protocol_source_sha256"):
        assert len(manifest[field]) == 64
    assert manifest["source_hashes"]
    assert all(len(value) == 64 for value in manifest["source_hashes"].values())
    assert all(len(clip["wav_sha256"]) == 64 for clip in manifest["clips"].values())
    assert all(entry["status"] == "not_listened" for entry in manifest["listening"].values())


def test_git_provenance_missing_executable(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "no-executables"))
    assert git_provenance(tmp_path) == {"source_commit": None, "source_dirty": None}


def test_git_provenance_checks_own_root_and_ignores_environment(tmp_path, monkeypatch):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "--allow-empty",
            "-m",
            "own checkout",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "unrelated.git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "other tree"))
    assert git_provenance(tmp_path) == {"source_commit": expected, "source_dirty": False}
    # A nested archive with an invalid marker must not inherit its parent's HEAD.
    nested = tmp_path / "nested"
    (nested / ".git").mkdir(parents=True)
    assert git_provenance(nested) == {"source_commit": None, "source_dirty": None}


def test_git_provenance_unborn_checkout(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    assert git_provenance(tmp_path) == {"source_commit": None, "source_dirty": None}
