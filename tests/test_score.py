import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from audio_as_code import Note, Pattern, Song, Track, midi_pitch
from audio_as_code.demo import demo_song


@pytest.mark.parametrize(
    "name,expected",
    [("C4", 60), ("A4", 69), ("Bb2", 46), ("F#3", 54), ("C-1", 0), ("G9", 127), (60, 60)],
)
def test_pitch_notation(name, expected):
    assert midi_pitch(name) == expected


@pytest.mark.parametrize("pitch", ["H4", "C10", "G#9", "Cb-1", 128, -1, True, 60.5])
def test_reject_invalid_pitch(pitch):
    with pytest.raises(ValueError):
        Note(pitch=pitch)


@pytest.mark.parametrize(
    "values",
    [
        {"duration": 0},
        {"start": -1},
        {"duration": float("inf")},
        {"velocity": 0},
        {"velocity": 1.1},
        {"start": float("nan")},
        {"start": "1"},
        {"start": True},
        {"duraton": 1},
    ],
)
def test_invalid_note_data(values):
    with pytest.raises(ValidationError):
        Note(**values)


def test_score_rejects_notes_outside_arrangement_and_duplicate_names():
    with pytest.raises(ValidationError, match="ends at beat"):
        Song(beats=1, tracks=[Track(name="Lead", notes=[Note(start=0.5)])])
    with pytest.raises(ValidationError, match="duplicate track"):
        Song(tracks=[Track(name="Lead"), Track(name="Lead")])


def test_version_and_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        Song(schema_version="2", tracks=[Track(name="Lead")])
    with pytest.raises(ValidationError):
        Song(tempo=120, tracks=[Track(name="Lead")])


def test_pattern_preserves_rests_chords_and_placement():
    pattern = Pattern.sequence([["C4", "E4"], None], step=0.5, gate=0.5)
    repeated = pattern.repeat(2)
    assert repeated.beats == 2
    assert [n.start for n in repeated.notes] == [0, 0, 1, 1]
    assert all(n.duration == 0.25 for n in repeated.notes)
    assert [n.pitch for n in pattern.transpose(12).notes] == [72, 76]
    assert pattern.notes[0].pitch == "C4"
    assert repeated.at(8)[-1].start == 9
    assert pattern.then(pattern).notes == repeated.notes


def test_pattern_validation():
    pattern = Pattern.sequence(["G9"])
    for count in [0, -1, True, 1.5]:
        with pytest.raises(ValueError):
            pattern.repeat(count)
    with pytest.raises(ValueError):
        pattern.transpose(1)
    with pytest.raises(ValueError):
        Pattern.sequence([None], velocity=0)
    with pytest.raises(ValueError):
        Pattern.sequence("C4")
    with pytest.raises(ValueError):
        Pattern.sequence(["C4"], gate=1.1)


def test_json_round_trip_and_schema_snapshot(tmp_path):
    song = demo_song()
    path = tmp_path / "score.json"
    song.save(path)
    assert Song.load(path) == song
    schema = Song.model_json_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(song.model_dump(mode="json"), schema)
    snapshot = Path(__file__).parents[1] / "schemas" / "song-v1.schema.json"
    assert json.loads(snapshot.read_text(encoding="utf-8")) == schema


def test_load_accepts_utf8_bom_and_save_emits_plain_utf8(tmp_path):
    song = demo_song()
    path = tmp_path / "score.json"
    path.write_text(song.model_dump_json(), encoding="utf-8-sig")
    assert Song.load(path) == song
    song.save(path)
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert Song.load(path) == song
