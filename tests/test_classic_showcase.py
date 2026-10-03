"""Complete score coverage and faithful classic arrangement contracts."""

from collections import Counter

import pytest

from examples.classic_showcase import BUILDERS, PLANS, _verify_source, pieces


@pytest.mark.parametrize(
    ("key", "notes", "beats", "bpm"),
    [
        ("fur_elise", 1041, 187, 72),
        ("cello_prelude", 656, 168, 80),
        ("turkish_march", 2811, 446, 112),
        ("greensleeves", 110, 97, 100),
        ("ode_to_joy", 245, 64, 100),
    ],
)
def test_classic_preserves_complete_source(key, notes, beats, bpm):
    song = BUILDERS["classic-" + key.replace("_", "-")]()
    source = pieces()[key]
    assert sum(len(track.notes) for track in song.tracks) == notes
    assert source["performance_notes"] == notes
    assert song.beats == beats + 0.75
    assert song.bpm == bpm
    assert song.seconds == pytest.approx((beats + 0.75) * 60 / bpm)
    assert max(note.start + note.duration for track in song.tracks for note in track.notes) == beats
    for track, (parts, voice, transpose, _gain, _pan) in zip(song.tracks, PLANS[key], strict=True):
        assert track.instrument == voice
        assert transpose == 0
        expected = Counter(tuple(row) for part in parts for row in source["parts"][part])
        actual = Counter(
            (note.pitch, note.start, note.duration, note.velocity) for note in track.notes
        )
        assert actual == expected
    _verify_source(song, key)


def test_repeat_maps_cover_complete_performed_timelines():
    for key, source in pieces().items():
        end = 0
        for section in source["repeat_expansion"]:
            assert section["performance_start_beat"] == end
            length = section["source_end_beat"] - section["source_start_beat"]
            assert length > 0
            assert section["performance_end_beat"] == end + length
            assert 0 <= section["source_start_beat"] < section["source_end_beat"]
            assert section["source_end_beat"] <= source["source_midi_beats"]
            end += length
        assert end == source["beats"]
        assert (end > source["source_midi_beats"]) == (key in {"fur_elise", "turkish_march"})


def test_named_arrangement_scopes_and_ode_unisons_are_explicit():
    source = pieces()
    assert "not the six-movement suite" in source["cello_prelude"]["scope"]
    assert "32 bars and pickup" in source["greensleeves"]["scope"]
    assert "16-bar SATB hymn arrangement" in source["ode_to_joy"]["scope"]
    assert "not Beethoven's Ninth Symphony" in source["ode_to_joy"]["scope"]
    assert source["ode_to_joy"]["source_midi_notes"] == 238
    assert source["ode_to_joy"]["performance_notes"] == 245
    assert set(source["ode_to_joy"]["parts"]) == {"soprano", "alto", "tenor", "bass"}
