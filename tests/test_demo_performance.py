"""Demo arrangements, full-source coverage, and safe incremental browser output."""

from collections import Counter

import pytest

from audio_as_code import Song, export_midi, get_instrument, list_instruments
from examples import instrument_browser as browser
from examples.classic_reimaginations import RECIPES, _role, arrange, export_all, pieces
from examples.famous_music import music_score


@pytest.mark.parametrize("voice", ["mandolin", "kalimba", "celesta", "recorder"])
def test_new_voice_music_stays_in_a_deliberate_sounding_register(voice, tmp_path):
    song, metadata = music_score(get_instrument(voice))
    assert len(song.tracks) == 1 and song.tracks[0].instrument == voice
    low, high = {
        "mandolin": (55, 88),
        "kalimba": (60, 84),
        "celesta": (60, 96),
        "recorder": (72, 96),
    }[voice]
    assert all(low <= note.pitch <= high for note in song.tracks[0].notes)
    assert metadata["excerpt"] and not metadata["complete"]
    assert metadata["license"] == "Public Domain" and metadata["credit"] and metadata["source"]
    export_midi(song, tmp_path / (voice + ".mid"))


@pytest.mark.parametrize("info", list_instruments(), ids=lambda info: info.id)
def test_auditions_are_dry_solo_scores_with_ending_space(info, tmp_path):
    for variant in ("note", "phrase"):
        song = browser.preview_score(info, variant)
        assert len(song.tracks) == 1 and song.tracks[0].instrument == info.id
        assert not song.effects and not song.tracks[0].effects
        assert song == browser.preview_score(info, variant)
        last_note = max(note.start + note.duration for note in song.tracks[0].notes)
        assert song.beat_to_seconds(last_note) + song.tracks[0].release_seconds < song.seconds
        if info.midi_note is None and variant == "phrase":
            notes = song.tracks[0].notes
            assert notes[0].pitch == notes[1].pitch == notes[-1].pitch
            assert notes[0].velocity < notes[1].velocity
            assert len({note.velocity for note in notes}) >= 4
        export_midi(song, tmp_path / f"{info.id}-{variant}.mid")


@pytest.mark.parametrize("key", RECIPES)
def test_reimaginations_account_for_every_complete_source_event(key, tmp_path):
    source = pieces()[key]
    song, mapping = arrange(key, source)
    assert song == arrange(key, source)[0]
    assert Song.model_validate_json(song.model_dump_json()) == song
    assert song.render_seconds < 300
    assert sum(item["source_events"] for item in mapping) == source["performance_notes"]
    for lane in mapping:
        part = lane["source_parts"][0]
        expected = Counter(
            (pitch + lane["transpose_semitones"], start)
            for pitch, start, _duration, _velocity in source["parts"][part]
            if _role(key, part, start)[0] == lane["instrument"]
        )
        track = next(track for track in song.tracks if track.name == lane["track"])
        assert {(note.pitch, note.start) for note in track.notes} == set(expected)
        assert sum(expected.values()) == lane["source_events"]
        assert track.release_seconds > 0
    export_midi(song, tmp_path / f"{key}.mid")


def test_reimagined_new_voices_keep_suitable_registers():
    expected = {
        "celesta": (60, 96),
        "kalimba": (60, 84),
        "mandolin": (55, 88),
        "recorder": (72, 96),
    }
    found = set()
    for key in RECIPES:
        song, _mapping = arrange(key)
        for track in song.tracks:
            if track.instrument in expected:
                low, high = expected[track.instrument]
                assert all(low <= note.pitch <= high for note in track.notes)
                found.add(track.instrument)
    assert found == set(expected)


def test_scores_only_invalidates_old_listening_manifest_but_preserves_audio(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"pieces": [{"id": "stale"}]}', encoding="utf-8")
    audio = tmp_path / "classic-fur-elise-reimagined.wav"
    audio.write_bytes(b"existing audio must survive score-only generation")
    original = audio.read_bytes()
    export_all(tmp_path, scores_only=True)
    assert not manifest.exists()
    assert audio.read_bytes() == original
    assert Song.load(tmp_path / "classic-fur-elise-reimagined.json") == arrange("fur_elise")[0]
    assert (tmp_path / "classic-fur-elise-reimagined.mid").read_bytes().startswith(b"MThd")


def test_engine_fingerprint_changes_when_dsp_bytes_change(tmp_path, monkeypatch):
    paths = [
        "src/audio_as_code/extended.py",
        "examples/instrument_browser.py",
        "examples/famous_music.py",
        "examples/music/excerpts.json",
    ]
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("initial", encoding="utf-8")
    monkeypatch.setattr(browser, "ROOT", tmp_path)
    monkeypatch.setattr(browser, "__file__", str(tmp_path / "examples/instrument_browser.py"))
    before = browser.engine_fingerprint()
    (tmp_path / paths[0]).write_text("changed synthesis", encoding="utf-8")
    assert browser.engine_fingerprint() != before


def test_browser_resume_reuses_only_matching_inputs_and_unmodified_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(browser, "list_instruments", lambda: [get_instrument("sine")])
    engine = ["first DSP"]
    monkeypatch.setattr(browser, "engine_fingerprint", lambda: engine[0])
    first = browser.main(tmp_path, instruments=["sine"])
    assert first["build"]["rendered"] == 3 and first["build"]["complete"]
    original_render = browser.render

    def forbidden_render(*args, **kwargs):
        raise AssertionError("Valid cached audio must not be rerendered")

    monkeypatch.setattr(browser, "render", forbidden_render)
    second = browser.main(tmp_path, instruments=["sine"], resume=True)
    assert second["build"]["reused"] == 3 and second["build"]["rendered"] == 0
    monkeypatch.setattr(browser, "render", original_render)
    (tmp_path / "midi/sine-note.mid").write_bytes(b"modified")
    repaired = browser.main(tmp_path, instruments=["sine"], resume=True)
    assert repaired["build"]["rendered"] == 1 and repaired["build"]["reused"] == 2
    engine[0] = "changed DSP"
    stale = browser.main(tmp_path, instruments=[], resume=True)
    assert stale["previews"] == {} and not stale["build"]["complete"]
    assert len(stale["build"]["missing_previews"]) == 3


def test_browser_rejects_unknown_subset_before_writing(tmp_path):
    with pytest.raises(ValueError, match="Unknown or unimplemented"):
        browser.main(tmp_path / "new", instruments=["not-a-voice"])
    assert not (tmp_path / "new").exists()
