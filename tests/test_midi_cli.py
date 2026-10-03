import json
import subprocess
import sys

import mido
import pytest

from audio_as_code import Note, Song, Track, export_midi
from audio_as_code.cli import main


def test_midi_tempo_percussion_and_retrigger_order(tmp_path):
    song = Song(
        bpm=120,
        beats=4,
        tracks=[
            Track(name="Melodia", notes=[Note(pitch="A4"), Note(pitch="A4", start=1)]),
            Track(name="Kick", instrument="kick", notes=[Note(pitch="C4")]),
        ],
    )
    path = tmp_path / "song.mid"
    export_midi(song, path)
    midi = mido.MidiFile(path, charset="utf-8")
    assert midi.type == 1 and midi.ticks_per_beat == 480
    assert midi.length == pytest.approx(2)
    assert midi.tracks[0][1].tempo == 500000
    events = [m for m in midi.tracks[1] if m.type in {"note_on", "note_off"}]
    assert [m.type for m in events] == ["note_on", "note_off", "note_on", "note_off"]
    assert events[1].time == 480 and events[2].time == 0
    drum = next(m for m in midi.tracks[2] if m.type == "note_on")
    assert drum.channel == 9 and drum.note == 36


def test_midi_rejects_ambiguous_overlaps_and_tiny_notes(tmp_path):
    for notes in [
        [Note(pitch="C4", duration=2), Note(pitch=60, start=1)],
        [Note(duration=0.00001)],
    ]:
        song = Song(tracks=[Track(name="Lead", notes=notes)])
        with pytest.raises(ValueError):
            export_midi(song, tmp_path / "invalid.mid")
        assert not (tmp_path / "invalid.mid").exists()


def test_midi_channel_limit_and_mute(tmp_path):
    with pytest.raises(ValueError, match="15 melodic"):
        export_midi(Song(tracks=[Track(name=str(i)) for i in range(16)]), tmp_path / "many.mid")
    export_midi(Song(tracks=[Track(name="Muted", gain=0, notes=[Note()])]), tmp_path / "mute.mid")
    midi = mido.MidiFile(tmp_path / "mute.mid")
    assert not any(m.type == "note_on" for track in midi.tracks for m in track)


def test_cli_end_to_end(tmp_path):
    score = tmp_path / "song.json"
    score.write_text(
        json.dumps(
            {
                "beats": 1,
                "tracks": [{"name": "Lead", "notes": [{"pitch": "C4"}]}],
            }
        ),
        encoding="utf-8",
    )
    for arguments in [
        ["validate", str(score)],
        [
            "render",
            str(score),
            "-o",
            str(tmp_path / "song.wav"),
            "--report",
            str(tmp_path / "report.json"),
        ],
        ["analyze", str(tmp_path / "song.wav")],
        ["midi", str(score), "-o", str(tmp_path / "song.mid")],
    ]:
        result = subprocess.run(
            [sys.executable, "-m", "audio_as_code", *arguments], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        assert isinstance(json.loads(result.stdout), dict)
        assert result.stderr == ""
    report = json.loads((tmp_path / "report.json").read_text())
    assert not report["wav"]["silent"]


def test_cli_invalid_score_and_arguments_are_json(tmp_path, capsys):
    score = tmp_path / "bad.json"
    score.write_text('{"tracks":[{"name":"Lead","notes":[{"duration":-1}]}]}')
    assert main(["validate", str(score)]) == 2
    result = capsys.readouterr()
    assert result.out == ""
    error = json.loads(result.err)
    assert error["error"] == "invalid_score"
    assert error["issues"][0]["path"] == ["tracks", 0, "notes", 0, "duration"]
    assert main(["render"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "operation_failed"


def test_cli_refuses_to_overwrite_score(tmp_path, capsys):
    score = tmp_path / "score.json"
    Song(tracks=[Track(name="Lead")]).save(score)
    original = score.read_bytes()
    assert main(["render", str(score), "-o", str(score)]) == 2
    assert score.read_bytes() == original
    assert "distinct" in json.loads(capsys.readouterr().err)["message"]
