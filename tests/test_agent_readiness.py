"""Exercise the public contract as a shell agent discovers, repairs and exports a score."""

import json
import shutil
import subprocess
import sys

import mido
import pytest

from audio_as_code import Note, Song, Track, inspect_score


@pytest.fixture(params=["module", "console"])
def command(request):
    if request.param == "module":
        return [sys.executable, "-m", "audio_as_code"]
    executable = shutil.which("aac")
    assert executable, "Install the package before running tests (uv sync --locked)"
    return [executable]


def _call(command, *arguments, status=0):
    result = subprocess.run(
        [*command, *map(str, arguments)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == status, result.stderr
    assert (result.stderr if status == 0 else result.stdout) == ""
    data = json.loads(result.stdout if status == 0 else result.stderr)
    assert isinstance(data, dict)
    return data


def test_agent_discovers_contract_and_round_trips_exports(command, tmp_path):
    for arguments in (["--help"], ["render", "--help"]):
        result = subprocess.run(
            [*command, *arguments], capture_output=True, text=True, timeout=60, check=False
        )
        assert result.returncode == 0 and result.stderr == ""
        assert "usage:" in result.stdout
    assert _call(command, "--version")["version"]
    catalog = _call(command, "instruments")
    assert catalog["synthesis_policy"] == "code_only"
    assert all(voice["status"] == "available" for voice in catalog["instruments"])
    assert {"marimba", "snare"} <= {voice["id"] for voice in catalog["instruments"]}
    schema_path = tmp_path / "score schema.json"
    schema = _call(command, "schema")
    _call(command, "schema", "-o", schema_path)
    assert json.loads(schema_path.read_text(encoding="utf-8")) == schema
    assert schema == Song.model_json_schema()

    source = tmp_path / "composi\u00e7\u00e3o with spaces.json"
    song = Song(
        title="An agent's \u65cb\u5f8b",
        beats=2,
        bpm=240,
        sample_rate=22050,
        seed=731,
        tracks=[
            Track(
                name="Melod\u00eda",
                instrument="marimba",
                notes=[Note(pitch="C4", duration=0.5), Note(pitch="E4", start=1, duration=0.5)],
            ),
            Track(name="Noise excitation", instrument="snare", notes=[Note(duration=0.5)]),
        ],
    )
    song.save(source)
    original = source.read_bytes()
    loaded = Song.load(source)
    roundtrip = tmp_path / "round trip.json"
    loaded.save(roundtrip)
    assert loaded == song
    assert roundtrip.read_bytes() == original
    assert _call(command, "validate", source)["valid"]
    inspection = _call(command, "inspect", source)
    assert inspection == inspect_score(song)
    assert inspection["readiness"]["render"]["ready"]
    assert inspection["readiness"]["midi"]["ready"]

    wav = tmp_path / "candidate one.wav"
    report_path = tmp_path / "render report.json"
    stems = tmp_path / "separate tracks"
    report = _call(command, "render", source, "-o", wav, "--report", report_path, "--stems", stems)
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert report["wav"] == _call(command, "analyze", wav)
    assert not report["wav"]["silent"]
    assert report["wav"]["frames"] == inspection["readiness"]["render"]["frames"]
    assert {item["track"] for item in report["stems"]} == {track.name for track in song.tracks}
    assert {path.name for path in stems.iterdir()} == {"01.wav", "02.wav"}
    second_wav = tmp_path / "candidate two.wav"
    second_report = _call(command, "render", roundtrip, "-o", second_wav)
    assert wav.read_bytes() == second_wav.read_bytes()
    assert report["score_sha256"] == second_report["score_sha256"]
    assert report["seed"] == second_report["seed"] == song.seed
    midi_path = tmp_path / "editable music.mid"
    midi_report = _call(command, "midi", source, "-o", midi_path)
    midi = mido.MidiFile(midi_path, charset="utf-8")
    assert midi_report["duration_seconds"] == pytest.approx(song.seconds)
    assert midi.length == pytest.approx(song.seconds)
    assert any(message.type == "note_on" for track in midi.tracks for message in track)
    assert source.read_bytes() == original


def test_agent_repairs_structured_failure_and_preserves_existing_outputs(command, tmp_path):
    source = tmp_path / "score with spaces.json"
    source.write_text('{"tracks":[{"name":"Lead","notes":[{"duration":-1}]}]}', encoding="utf-8")
    error = _call(command, "validate", source, status=2)
    assert error["error"] == "invalid_score"
    assert error["issues"][0]["path"] == ["tracks", 0, "notes", 0, "duration"]
    assert error["hint"]
    data = json.loads(source.read_text(encoding="utf-8"))
    data["tracks"][0]["notes"][0]["duration"] = 1
    source.write_text(json.dumps(data), encoding="utf-8")
    assert _call(command, "validate", source)["valid"]

    for arguments in ([], ["render"], ["unknown-command"], ["instruments", "--family", "wrong"]):
        error = _call(command, *arguments, status=2)
        assert error["error"] == "operation_failed"
        assert error["message"] and error["hint"]
    assert _call(command, "validate", tmp_path / "missing.json", status=2)["error"] == (
        "operation_failed"
    )
    for payload in ('{"tracks":', '{"tracks": []}', '{"bpm": NaN, "tracks":[{"name":"A"}]}'):
        source.write_text(payload, encoding="utf-8")
        assert _call(command, "validate", source, status=2)["error"] == "invalid_score"

    output = tmp_path / "preserved output"
    sentinel = b"Keep the previous candidate."
    for song, operation, blocker in (
        (Song(beats=602, tracks=[Track(name="Long")]), "render", "render"),
        (
            Song(tracks=[Track(name="Overlap", notes=[Note(duration=2), Note(start=1)])]),
            "midi",
            "midi",
        ),
    ):
        song.save(source)
        original = source.read_bytes()
        output.write_bytes(sentinel)
        inspection = _call(command, "inspect", source)
        assert inspection["validation"]["valid"]
        assert not inspection["readiness"][blocker]["ready"]
        assert any(issue["severity"] == "error" for issue in inspection["issues"])
        assert _call(command, operation, source, "-o", output, status=2)["error"] == (
            "operation_failed"
        )
        assert source.read_bytes() == original
        assert output.read_bytes() == sentinel
