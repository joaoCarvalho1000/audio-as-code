"""MIDI loss diagnostics for opt-in synthesized articulations."""

import pytest

from audio_as_code import Note, Song, Track, export_midi, inspect_score


@pytest.mark.parametrize("scope", ["track", "note"])
def test_articulation_warns_without_changing_midi_notes(scope, tmp_path):
    plain = Song(
        beats=2,
        tracks=[Track(name="Flute", instrument="flute", notes=[Note(pitch="A4")])],
    )
    data = plain.model_dump()
    target = data["tracks"][0]
    if scope == "note":
        target = target["notes"][0]
    target["articulation"] = "soft"
    articulated = Song.model_validate(data)

    plain_path, articulated_path = tmp_path / "plain.mid", tmp_path / "articulated.mid"
    plain_report = export_midi(plain, plain_path)
    report = export_midi(articulated, articulated_path)
    assert plain_path.read_bytes() == articulated_path.read_bytes()
    assert "articulations" not in " ".join(plain_report["warnings"])
    assert "Modeled note articulations are not exported." in " ".join(report["warnings"])

    inspected = inspect_score(articulated)
    losses = [
        issue for issue in inspected["issues"] if issue["code"] == "midi_articulations_not_exported"
    ]
    assert len(losses) == 1
    assert losses[0]["path"] == ["tracks", 0]
    assert inspected["readiness"]["midi"]["ready"]
    assert not any(
        issue["code"] == "midi_articulations_not_exported"
        for issue in inspect_score(plain)["issues"]
    )
