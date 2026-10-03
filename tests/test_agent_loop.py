"""The tutorial must not hand an agent a success result after an export failure."""

import importlib.util
from pathlib import Path

import pytest

from audio_as_code import Note, Song, Track

SCRIPT = Path(__file__).resolve().parents[1] / "docs/site/examples/05_agent_loop.py"


def example():
    spec = importlib.util.spec_from_file_location("agent_loop_example", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_loop_reports_actual_midi_export_failure(tmp_path):
    song = Song(
        beats=0.25,
        sample_rate=22050,
        tracks=[
            Track(
                name="Overlap",
                notes=[
                    Note(duration=0.25),
                    Note(start=0.125, duration=0.125),
                ],
            )
        ],
    )
    result = example().candidate(tmp_path, "overlap", song.model_dump(mode="json"))
    assert result["ok"] is False
    assert result["error"]["error"] == "operation_failed"
    assert "overlapping MIDI pitch" in result["error"]["message"]
    assert (tmp_path / "overlap/song.wav").is_file()
    assert not (tmp_path / "overlap/song.mid").exists()


@pytest.mark.parametrize("failed_command", ["validate", "render", "midi", "analyze"])
def test_agent_loop_preserves_diagnostic_and_stops_on_failure(
    tmp_path, monkeypatch, failed_command
):
    module = example()
    calls = []
    diagnostic = {"error": "operation_failed", "message": "synthetic command failure"}

    def aac(command, *arguments):
        calls.append(command)
        return (2, diagnostic) if command == failed_command else (0, {})

    monkeypatch.setattr(module, "aac", aac)
    result = module.candidate(tmp_path, "candidate", {})
    assert result == {"ok": False, "error": diagnostic}
    assert calls[-1] == failed_command
