import mido
import pytest

from audio_as_code import Note, Song, Track, export_midi


def test_plain_melodic_score_only_warns_about_receiver_sound(tmp_path):
    report = export_midi(Song(tracks=[Track(name="Lead", notes=[Note()])]), tmp_path / "plain.mid")
    assert report["warnings"] == [
        "MIDI preserves notes and tempo; sounds depend on the receiving synthesizer."
    ]


@pytest.mark.parametrize(
    "owner,field,value,expected",
    [
        ("track", "tone", {"brightness": 0.7}, "tone controls"),
        (
            "track",
            "automation",
            [{"parameter": "pan", "points": [{"beat": 0, "value": 0.2}]}],
            "automation",
        ),
        (
            "song",
            "automation",
            [{"parameter": "master_gain", "points": [{"beat": 0, "value": 0.2}]}],
            "automation",
        ),
        ("track", "effects", [{"type": "delay"}], "effects"),
        ("song", "effects", [{"type": "reverb"}], "effects"),
        ("track", "release_seconds", 0.2, "Note releases"),
        ("note", "release_seconds", 0.2, "Note releases"),
    ],
)
def test_only_present_audio_feature_is_warned_and_midi_bytes_are_unchanged(
    owner, field, value, expected, tmp_path
):
    plain = Song(tracks=[Track(name="Lead", instrument="marimba", notes=[Note()])])
    data = plain.model_dump(mode="json")
    target = data if owner == "song" else data["tracks"][0]
    if owner == "note":
        target = target["notes"][0]
    target[field] = value
    expressive = Song.model_validate(data)
    baseline = tmp_path / "plain.mid"
    changed = tmp_path / "expressive.mid"
    export_midi(plain, baseline)
    report = export_midi(expressive, changed)
    assert baseline.read_bytes() == changed.read_bytes()
    warning = " ".join(report["warnings"])
    assert "receiving synthesizer" in warning
    assert expected in warning and "not exported" in warning
    for unrelated in {"tone controls", "automation", "effects", "Note releases"} - {expected}:
        assert unrelated not in warning
    assert "Percussion" not in warning
    assert "Tempo changes" not in warning


def test_percussion_and_tempo_caveats_follow_actual_score_features(tmp_path):
    song = Song.model_validate(
        {
            "tempo_map": [{"beat": 0.333, "bpm": 100}],
            "tracks": [{"name": "Kick", "instrument": "kick", "notes": [{"pitch": 36}]}],
        }
    )
    path = tmp_path / "drums.mid"
    report = export_midi(song, path)
    warning = " ".join(report["warnings"])
    assert "shared channel 10" in warning
    assert "grouped" in warning
    assert "Tempo changes are rounded" in warning
    assert "not exported" not in warning
    assert warning.index("receiving synthesizer") < warning.index("Percussion")
    assert warning.index("Percussion") < warning.index("Tempo changes")
    midi = mido.MidiFile(path)
    assert next(m for m in midi.tracks[1] if m.type == "note_on").channel == 9
    assert [m.time for m in midi.tracks[0] if m.type == "set_tempo"] == [0, 160]


def test_zero_explicit_release_does_not_warn_about_release_loss(tmp_path):
    song = Song(tracks=[Track(name="Lead", notes=[Note(release_seconds=0)])])
    report = export_midi(song, tmp_path / "no-release.mid")
    assert "releases" not in " ".join(report["warnings"])
