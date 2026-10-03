import importlib
import json
import shutil
import subprocess
import sys

import pytest
from pydantic import ValidationError

from audio_as_code import (
    Automation,
    AutomationPoint,
    Delay,
    Note,
    Song,
    TempoChange,
    Tone,
    Track,
    export_midi,
)
from audio_as_code.cli import main
from audio_as_code.inspection import inspect_score


def _codes(report):
    return {issue["code"] for issue in report["issues"]}


def test_inspection_measures_tempo_pitch_polyphony_and_release_without_mutation(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Inspection must not render, export, or save")

    monkeypatch.setattr(importlib.import_module("audio_as_code.render"), "render_audio", unexpected)
    monkeypatch.setattr(importlib.import_module("audio_as_code.midi"), "export_midi", unexpected)
    monkeypatch.setattr(Song, "save", unexpected)
    song = Song(
        beats=4,
        bpm=120,
        tempo_map=[TempoChange(beat=2, bpm=60)],
        tracks=[
            Track(
                name="Lead",
                notes=[
                    Note(pitch="C4", start=0, duration=2),
                    Note(pitch="G4", start=1, duration=1),
                    Note(pitch=60, start=2, duration=2, release_seconds=1),
                ],
                effects=[Delay(time_seconds=0.5, repeats=2)],
            ),
            Track(name="Empty"),
        ],
    )
    before = song.model_dump_json()
    report = inspect_score(song)
    assert report == inspect_score(song)
    assert json.loads(json.dumps(report, allow_nan=False)) == report
    assert song.model_dump_json() == before
    assert report["summary"]["duration_seconds"] == 3
    assert report["summary"]["render_duration_seconds"] == 5
    assert report["summary"]["tail_seconds"] == 2
    assert report["summary"]["max_note_polyphony"] == 2
    lead, empty = report["tracks"]
    assert lead["written_pitch_range"] == {"min": 60, "max": 67}
    assert lead["first_note_seconds"] == 0
    assert lead["last_note_end_seconds"] == 3
    assert lead["dry_end_seconds"] == 4
    assert lead["effect_end_seconds"] == 5
    assert lead["max_note_polyphony"] == 2
    assert empty["first_note_beat"] is None
    assert empty["written_pitch_range"] is None
    assert empty["max_note_polyphony"] == 0
    assert report["readiness"]["render"]["ready"]
    assert report["readiness"]["midi"]["ready"]
    assert {"empty_track", "midi_releases_not_exported", "midi_effects_not_exported"} <= _codes(
        report
    )


@pytest.mark.parametrize("release,ready", [(0, True), (0.001, False)])
def test_render_limit_includes_release_tail(release, ready):
    song = Song(
        beats=600,
        tracks=[
            Track(
                name="Lead",
                notes=[
                    Note(start=599, release_seconds=release),
                ],
            )
        ],
    )
    report = inspect_score(song)
    assert report["validation"]["valid"]
    assert report["readiness"]["render"]["ready"] is ready
    assert ("render_duration_limit" in _codes(report)) is (not ready)
    assert report["readiness"]["midi"]["ready"]


@pytest.mark.parametrize(
    "song,code",
    [
        (Song(tracks=[Track(name=str(i)) for i in range(16)]), "midi_melodic_channel_limit"),
        (
            Song(tracks=[Track(name="Lead", notes=[Note(duration=2), Note(start=1)])]),
            "midi_same_pitch_overlap",
        ),
        (
            Song(tracks=[Track(name="Lead", gain=0, notes=[Note(duration=2), Note(start=1)])]),
            "midi_same_pitch_overlap",
        ),
        (Song(tracks=[Track(name="Lead", notes=[Note(duration=0.00001)])]), "midi_note_below_tick"),
        (Song(beats=0.00001, tracks=[Track(name="Empty")]), "midi_duration_out_of_range"),
        (
            Song(tracks=[Track(name="A", instrument="kick"), Track(name="B", instrument="kick")]),
            "midi_duplicate_drum_instrument",
        ),
        (
            Song(
                tracks=[
                    Track(name="Kick", instrument="kick", notes=[Note(pitch=90)]),
                    Track(name="Kit", instrument="drum_machine", notes=[Note(pitch=36)]),
                ]
            ),
            "midi_percussion_pitch_overlap",
        ),
    ],
)
def test_static_midi_blockers_match_export(song, code, tmp_path):
    report = inspect_score(song)
    assert report["validation"]["valid"]
    assert not report["readiness"]["midi"]["ready"]
    assert code in _codes(report)
    assert next(issue for issue in report["issues"] if issue["code"] == code)["severity"] == "error"
    with pytest.raises(ValueError):
        export_midi(song, tmp_path / "blocked.mid")
    assert not (tmp_path / "blocked.mid").exists()


@pytest.mark.parametrize("kit_start,kick_gain", [(1, 0.6), (0, 0)])
def test_distinct_percussion_tracks_can_share_channel_without_collision(
    kit_start, kick_gain, tmp_path
):
    song = Song(
        tracks=[
            Track(name="Kick", instrument="kick", gain=kick_gain, notes=[Note(pitch=90)]),
            Track(name="Kit", instrument="drum_machine", notes=[Note(pitch=36, start=kit_start)]),
            Track(name="Snare", instrument="snare", notes=[Note(pitch=36)]),
        ]
    )
    report = inspect_score(song)
    assert report["readiness"]["midi"]["ready"]
    assert report["readiness"]["midi"]["melodic_tracks"] == 0
    assert report["tracks"][0]["written_pitch_range"] == {"min": 90, "max": 90}
    assert report["tracks"][0]["midi_pitch_range"] == {"min": 36, "max": 36}
    export_midi(song, tmp_path / "percussion.mid")


def test_tick_and_sample_rounding_reported_without_quality_claims():
    song = Song(tracks=[Track(name="Lead", notes=[Note(duration=0.00000001)])])
    report = inspect_score(song)
    assert report["readiness"]["render"]["ready"]
    assert {
        "render_note_below_sample",
        "midi_note_below_tick",
        "midi_note_timing_quantized",
    } <= _codes(report)
    assert all(
        issue["path"] == ["tracks", 0, "notes", 0]
        for issue in report["issues"]
        if issue["code"] == "render_note_below_sample"
    )
    tiny = inspect_score(Song(beats=0.00000001, tracks=[Track(name="Empty")]))
    assert not tiny["readiness"]["render"]["ready"]
    assert "render_below_one_sample" in _codes(tiny)


def test_unchecked_invalid_model_is_revalidated():
    song = Song(tracks=[Track(name="Lead")]).model_copy(update={"bpm": -1})
    with pytest.raises(ValidationError):
        inspect_score(song)


def test_master_effect_tail_and_midi_control_losses_are_reported():
    song = Song(
        beats=598,
        effects=[Delay(time_seconds=1, repeats=2)],
        automation=[
            Automation(parameter="master_gain", points=[AutomationPoint(beat=0, value=0.5)])
        ],
        tempo_map=[TempoChange(beat=0.001, bpm=120)],
        tracks=[Track(name="Guitar", instrument="guitar", tone=Tone(brightness=0.7))],
    )
    report = inspect_score(song)
    assert report["summary"]["duration_seconds"] == pytest.approx(299)
    assert report["summary"]["render_duration_seconds"] == pytest.approx(301)
    assert not report["readiness"]["render"]["ready"]
    assert report["readiness"]["midi"]["ready"]
    assert {
        "midi_tone_not_exported",
        "midi_effects_not_exported",
        "midi_automation_not_exported",
        "midi_tempo_timing_quantized",
    } <= _codes(report)


def test_pitched_percussion_uses_melodic_budget_but_distinct_drums_do_not(tmp_path):
    tracks = [Track(name=str(i), instrument="marimba") for i in range(15)]
    tracks.extend([Track(name="Kick", instrument="kick"), Track(name="Snare", instrument="snare")])
    song = Song(tracks=tracks)
    report = inspect_score(song)
    assert report["readiness"]["midi"]["melodic_tracks"] == 15
    assert report["readiness"]["midi"]["ready"]
    assert not report["tracks"][0]["midi_percussion"]
    export_midi(song, tmp_path / "fifteen.mid")


def test_cli_inspection_is_read_only_and_preserves_validation_contract(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "score.json"
    Song(beats=602, tracks=[Track(name="Long")]).save(path)
    before = path.read_bytes()
    assert main(["inspect", str(path)]) == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert not output.err
    assert report["validation"]["valid"]
    assert not report["readiness"]["render"]["ready"]
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    path.write_text('{"tracks":[{"name":"Bad","notes":[{"duration":-1}]}]}')
    assert main(["inspect", str(path)]) == 2
    output = capsys.readouterr()
    assert not output.out
    error = json.loads(output.err)
    assert error["error"] == "invalid_score"
    assert error["issues"][0]["path"] == ["tracks", 0, "notes", 0, "duration"]
    assert main(["inspect", str(tmp_path / "missing.json")]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "operation_failed"


def test_inspect_both_cli_entrypoints(tmp_path):
    score = tmp_path / "score with spaces.json"
    Song(tracks=[Track(name="Lead", notes=[Note()])]).save(score)
    executable = shutil.which("aac")
    assert executable, "Install the package before running tests (uv sync --locked)"
    reports = []
    for command in ([sys.executable, "-m", "audio_as_code"], [executable]):
        result = subprocess.run([*command, "inspect", str(score)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
        reports.append(json.loads(result.stdout))
    assert reports[0] == reports[1]
    assert list(tmp_path.iterdir()) == [score]
