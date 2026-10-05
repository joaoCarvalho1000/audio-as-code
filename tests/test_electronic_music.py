"""Complete source coverage and real export contracts for the genre arrangements."""

import pytest

from audio_as_code import export_midi, inspect_score
from examples.electronic_music import PARTS, STYLES, genre_song, source_piece


@pytest.mark.parametrize("style", STYLES)
def test_genre_arrangements_preserve_every_source_event_and_export(style, tmp_path):
    source = source_piece()
    song = genre_song(style)
    assert song == genre_song(style)
    assert song.beats == source["beats"]
    for part in PARTS:
        track = next(t for t in song.tracks if t.name == part)
        assert len(track.notes) == len(source["parts"][part])
        for note, (pitch, start, duration, _) in zip(
            track.notes, source["parts"][part], strict=True
        ):
            assert (note.start, note.duration) == (start, duration)
            assert (note.pitch - pitch) % 12 == 0
    assert not [i for i in inspect_score(song)["issues"] if i["severity"] == "error"]
    export_midi(song, tmp_path / f"{style}.mid")
