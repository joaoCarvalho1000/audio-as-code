import pytest

from audio_as_code import Song, export_midi, list_instruments
from examples.famous_music import ENSEMBLES, PERCUSSION, SOLOS, music_score, pieces


def test_every_catalog_voice_has_exactly_one_featured_music_demo():
    groups = [set(SOLOS), set(ENSEMBLES), PERCUSSION]
    assert set.union(*groups) == {info.id for info in list_instruments()}
    assert sum(len(group) for group in groups) == len(set.union(*groups))


@pytest.mark.parametrize("info", list_instruments(), ids=lambda info: info.id)
def test_music_arrangements_are_valid_repeatable_and_midi_exportable(info, tmp_path):
    song, credits = music_score(info)
    assert song == music_score(info)[0]
    assert Song.model_validate_json(song.model_dump_json()) == song
    assert any(track.instrument == info.id and track.notes for track in song.tracks)
    assert 10 < song.seconds < 25
    assert credits["license"] == "Public Domain"
    path = tmp_path / f"{info.id}.mid"
    export_midi(song, path)  # Checks retrigger overlaps, kit pitches and channel allocation.
    assert path.read_bytes().startswith(b"MThd")


def test_recognizable_openings_preserve_score_pitches_and_rhythm():
    source = pieces()
    assert source["fur_elise"]["parts"]["melody"][:5] == [
        [76, 0, 0.25],
        [75, 0.25, 0.25],
        [76, 0.5, 0.25],
        [75, 0.75, 0.25],
        [76, 1, 0.25],
    ]
    assert [row[0] for row in source["cello_prelude"]["parts"]["melody"][:8]] == [
        43,
        50,
        59,
        57,
        59,
        50,
        59,
        50,
    ]
    assert [row[0] for row in source["ode_to_joy"]["parts"]["melody"][:8]] == [
        71,
        71,
        72,
        74,
        74,
        72,
        71,
        69,
    ]
