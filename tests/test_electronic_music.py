"""Complete source coverage and real export contracts for the genre arrangements."""

import pytest

from audio_as_code import export_midi, inspect_score
from examples.electronic_music import (
    INTRO_BEATS,
    OUTRO_BEATS,
    PARTS,
    STYLES,
    genre_song,
    song_sections,
    source_piece,
)


@pytest.mark.parametrize("style", STYLES)
def test_genre_arrangements_preserve_every_source_event_and_export(style, tmp_path):
    source = source_piece()
    song = genre_song(style)
    assert song == genre_song(style)
    assert song.beats == INTRO_BEATS + source["beats"] + OUTRO_BEATS
    assert song.render_seconds < 300
    for part in PARTS:
        track = next(t for t in song.tracks if t.name == part)
        assert len(track.notes) == len(source["parts"][part])
        for note, (pitch, start, duration, _) in zip(
            track.notes, source["parts"][part], strict=True
        ):
            # The whole hymn is shifted by the intro; rhythm and pitch class are kept.
            assert (note.start - INTRO_BEATS, note.duration) == (start, duration)
            assert (note.pitch - pitch) % 12 == 0
    assert not [i for i in inspect_score(song)["issues"] if i["severity"] == "error"]
    export_midi(song, tmp_path / f"{style}.mid")


@pytest.mark.parametrize("style", STYLES)
def test_arrangement_form_has_breakdown_drop_and_ending_tail(style):
    song = genre_song(style)
    sections = {name: (start, end) for name, start, end in song_sections(style)}
    kick = next(t for t in song.tracks if t.name == "Kick")
    breakdown = sections["Breakdown"]
    assert not [n for n in kick.notes if breakdown[0] <= n.start < breakdown[1]]
    assert [n for n in kick.notes if sections["Drop"][0] <= n.start < sections["Drop"][1]]
    double = next(t for t in song.tracks if t.name == "Drop lead double")
    assert min(n.start for n in double.notes) >= sections["Drop"][0]
    last = max(n.start + n.duration for t in song.tracks for n in t.notes)
    assert last <= song.beats and song.render_seconds > song.seconds
