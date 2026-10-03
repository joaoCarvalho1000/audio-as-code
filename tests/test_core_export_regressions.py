import json
import struct
import wave

import mido
import pytest

from audio_as_code import Note, Song, Track, analyze_wav, export_midi, render
from audio_as_code.cli import main


@pytest.mark.parametrize("reverse_tracks", [False, True])
def test_shared_percussion_retrigger_survives_midi_merge(tmp_path, reverse_tracks):
    tracks = [
        Track(name="Kit", instrument="drum_machine", notes=[Note(pitch=36, start=1)]),
        Track(name="Kick", instrument="kick", notes=[Note(start=0)]),
    ]
    if reverse_tracks:
        tracks.reverse()
    song = Song(beats=2, tracks=tracks)
    destination = tmp_path / "percussion.mid"
    report = export_midi(song, destination)
    midi = mido.MidiFile(destination)
    events = [event for event in mido.merge_tracks(midi.tracks) if event.type.startswith("note_")]
    assert [event.type for event in events] == ["note_on", "note_off", "note_on", "note_off"]
    assert [event.time for event in events] == [0, 480, 0, 480]
    assert all(event.channel == 9 and event.note == 36 for event in events)
    assert [track.name for track in midi.tracks] == ["Tempo", *(track.name for track in tracks)]
    assert midi.length == pytest.approx(1)
    assert "grouped" in " ".join(report["warnings"])


def test_empty_first_percussion_track_preserves_later_notes(tmp_path):
    song = Song(
        beats=2,
        tracks=[
            Track(name="Empty", instrument="hat"),
            Track(name="Kick", instrument="kick", notes=[Note()]),
            Track(name="Snare", instrument="snare", notes=[Note(start=1)]),
        ],
    )
    destination = tmp_path / "drums.mid"
    export_midi(song, destination)
    midi = mido.MidiFile(destination)
    assert [event.note for event in midi.tracks[1] if event.type == "note_on"] == [36, 38]
    assert not any(event.type == "note_on" for track in midi.tracks[2:] for event in track)


@pytest.mark.parametrize("alias_kind", ["mix_stem", "stem_stem"])
def test_render_rejects_hardlink_aliases_before_writing(tmp_path, alias_kind):
    mix = tmp_path / "mix.wav"
    first_stem = tmp_path / "01.wav"
    second_stem = tmp_path / "02.wav"
    original = b"existing file must survive"
    first_stem.write_bytes(original)
    alias = mix if alias_kind == "mix_stem" else second_stem
    alias.hardlink_to(first_stem)
    song = Song(beats=1, tracks=[Track(name="One"), Track(name="Two")])
    with pytest.raises(ValueError, match="same path or file"):
        render(song, mix, stems_dir=tmp_path)
    assert first_stem.read_bytes() == original
    assert alias.read_bytes() == original
    if alias_kind == "stem_stem":
        assert not mix.exists()


def test_analyze_rejects_partial_pcm_frame(tmp_path):
    path = tmp_path / "partial.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(22050)
        stream.writeframes(struct.pack("<hhh", 1, 2, 3))
    with pytest.raises(ValueError, match="incomplete PCM frame"):
        analyze_wav(path)


def test_zero_rate_wav_returns_structured_cli_error(tmp_path, capsys):
    path = tmp_path / "zero-rate.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(22050)
        stream.writeframes(struct.pack("<h", 1))
    malformed = bytearray(path.read_bytes())
    struct.pack_into("<II", malformed, 24, 0, 0)  # Sample and byte rates.
    path.write_bytes(malformed)
    with pytest.raises(ValueError, match="sample rate must be positive"):
        analyze_wav(path)
    assert main(["analyze", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    diagnostic = json.loads(captured.err)
    assert diagnostic["error"] == "operation_failed"
    assert "sample rate" in diagnostic["message"]
    assert path.read_bytes() == malformed
