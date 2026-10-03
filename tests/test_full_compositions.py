"""Content/export contracts for the arranged original compositions."""

import importlib.util
import inspect
import json
from pathlib import Path

import mido
import pytest

from audio_as_code import Song, export_midi
from audio_as_code.instruments import DRUM_NOTES

SOURCE = Path(__file__).parents[1] / "examples" / "full_compositions.py"
SPEC = importlib.util.spec_from_file_location("full_compositions", SOURCE)
compositions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compositions)


@pytest.mark.parametrize("piece_id", compositions.BUILDERS)
def test_form_duration_and_deterministic_score(piece_id):
    builder = compositions.BUILDERS[piece_id]
    song = builder()
    assert song == builder()
    assert Song.model_validate_json(song.model_dump_json()) == song
    assert song.sample_rate == 44100
    assert 75 <= song.seconds <= 150
    form = compositions.sections(piece_id)
    assert form[0]["start_beat"] == 0
    assert form[-1]["end_beat"] == song.beats
    assert all(a["end_beat"] == b["start_beat"] for a, b in zip(form, form[1:], strict=False))
    assert sum(t.instrument not in DRUM_NOTES for t in song.tracks) <= 15
    # Verify meaningful orchestration changes, not merely renamed loop sections.
    textures = set()
    for section in form:
        active = tuple(
            t.name
            for t in song.tracks
            if any(section["start_beat"] <= n.start < section["end_beat"] for n in t.notes)
        )
        textures.add(active)
    assert len(textures) >= 3
    # Last bar is an explicit sustained cadence without new rhythmic events.
    last_bar = song.beats - compositions.FORMS[piece_id][0]
    assert not any(n.start > last_bar for t in song.tracks for n in t.notes)


@pytest.mark.parametrize("piece_id", compositions.BUILDERS)
def test_midi_has_balanced_events_and_score_duration(piece_id, tmp_path):
    song = compositions.BUILDERS[piece_id]()
    path = tmp_path / "piece.mid"
    export_midi(song, path)
    midi = mido.MidiFile(path)
    assert midi.type == 1
    assert midi.length == pytest.approx(song.seconds, abs=0.001)
    active = set()
    ons = 0
    for message in mido.merge_tracks(midi.tracks):
        if message.type not in ("note_on", "note_off"):
            continue
        key = (message.channel, message.note)
        if message.type == "note_on" and message.velocity:
            assert key not in active
            active.add(key)
            ons += 1
        else:
            assert key in active
            active.remove(key)
    assert not active
    assert ons == sum(len(t.notes) for t in song.tracks)


def test_score_package_and_source_rebuild(tmp_path):
    pieces = compositions.export_all(tmp_path, scores_only=True)
    manifest = json.loads((tmp_path / "scores-manifest.json").read_text())
    assert manifest["pieces"] == pieces
    assert not (tmp_path / "manifest.json").exists()
    assert (tmp_path / "full_compositions.py").read_bytes() == SOURCE.read_bytes()
    for piece in pieces:
        song = Song.load(tmp_path / piece["score"])
        assert piece["sections"] == compositions.sections(piece["id"])
        assert piece["duration_seconds"] == song.seconds
        assert (tmp_path / piece["midi"]).is_file()
        body = inspect.getsource(compositions.BUILDERS[piece["id"]])
        excerpt = body.split("# excerpt-start\n")[1].split("# excerpt-end")[0]
        assert piece["code_excerpt"] == inspect.cleandoc(excerpt)
        assert piece["source_function"] == compositions.BUILDERS[piece["id"]].__name__


def test_copied_source_builds_same_scores(tmp_path):
    compositions.export_all(tmp_path, scores_only=True)
    spec = importlib.util.spec_from_file_location(
        "copied_compositions", tmp_path / "full_compositions.py"
    )
    copied = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copied)
    for piece_id, builder in compositions.BUILDERS.items():
        assert copied.BUILDERS[piece_id]() == builder()


def test_scores_only_invalidates_existing_listening_package(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"pieces": []}')
    compositions.export_all(tmp_path, scores_only=True)
    assert not manifest.exists()
    assert (tmp_path / "scores-manifest.json").is_file()


def test_failed_render_does_not_leave_stale_listening_manifest(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"pieces": []}')

    def fail_render(*args, **kwargs):
        assert not manifest.exists()
        raise RuntimeError("render interrupted")

    monkeypatch.setattr(compositions, "render", fail_render)
    with pytest.raises(RuntimeError, match="render interrupted"):
        compositions.export_all(tmp_path)
    assert not manifest.exists()
