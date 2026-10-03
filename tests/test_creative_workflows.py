"""Media timing, constrained revisions, and portable creative delivery contracts."""

import importlib.util
import json
import subprocess
import sys
import wave
from pathlib import Path

import mido
import numpy as np
import pytest

from audio_as_code import Song, export_midi, inspect_score, render

SOURCE = Path(__file__).resolve().parents[1] / "examples/creative_workflows.py"
SPEC = importlib.util.spec_from_file_location("creative_workflows", SOURCE)
workflows = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflows)


@pytest.mark.parametrize("brief,seconds", [("video", 30), ("game", 12), ("presentation", 9)])
def test_original_and_revision_keep_media_timing_and_midi(brief, seconds, tmp_path):
    original = getattr(workflows, brief)()
    revised = workflows.revise(original, brief)
    assert all(workflows.revision_contract(original, revised, brief).values())
    assert original == getattr(workflows, brief)()
    for version, song in (("v1", original), ("v2", revised)):
        assert song.seconds == song.render_seconds == seconds
        assert inspect_score(song)["readiness"]["midi"]["ready"]
        output = tmp_path / f"{version}.mid"
        export_midi(song, output)
        assert mido.MidiFile(output).length == pytest.approx(seconds, abs=0.001)
    if brief == "video":
        cue = next(track for track in original.tracks if track.name == "Reveal")
        assert {original.beat_to_seconds(note.start) for note in cue.notes} == {20}


def test_preservation_check_rejects_accidental_melody_edit():
    original = workflows.video()
    revised = workflows.revise(original, "video").model_dump(mode="json")
    revised["tracks"][0]["notes"][0]["pitch"] += 1
    with pytest.raises(AssertionError, match="Melody_unchanged"):
        workflows.revision_contract(original, Song.model_validate(revised), "video")


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_actual_game_pcm_loop_has_continuous_join_and_identical_cycles(version, tmp_path):
    song = workflows.game()
    if version == "v2":
        song = workflows.revise(song, "game")
    path = tmp_path / "loop.wav"
    render(song, path)
    checks = workflows.verify_loop(path, tmp_path / "two-cycles.wav")
    assert checks["join_jump_pcm"] == checks["join_local_step_pcm"] == 0
    assert checks["two_cycles_seconds"] == 24
    assert checks["cycles_identical"]
    assert checks["first_frame_pcm"] == checks["last_frame_pcm"] == [0, 0]


def test_loop_check_rejects_a_discontinuous_join(tmp_path):
    path = tmp_path / "broken.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(np.array([[0, 0], [1000, 1000], [500, 500]], dtype="<i2").tobytes())
    with pytest.raises(AssertionError, match="join_jump_pcm"):
        workflows.verify_loop(path, tmp_path / "two.wav")


def test_portable_composer_rebuild_and_existing_candidate_preserved(tmp_path):
    output = tmp_path / "candidate with spaces"
    command = [
        sys.executable,
        str(SOURCE),
        str(output),
        "--scores-only",
        "--brief",
        "game",
        "--version",
        "v2",
    ]
    first = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert first.returncode == 0, first.stderr
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["scores_only"] is True
    assert set(manifest["briefs"]) == {"game"}
    artifacts = manifest["briefs"]["game"]["artifacts"]["v2"]
    for path in artifacts.values():
        assert not Path(path).is_absolute()
        assert (output / path).is_file()
    second_output = tmp_path / "copied composer result"
    copied = subprocess.run(
        [
            sys.executable,
            str(output / artifacts["composer.py"]),
            str(second_output),
            "--scores-only",
            "--brief",
            "game",
            "--version",
            "v2",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert copied.returncode == 0, copied.stderr
    assert (second_output / artifacts["score.json"]).read_bytes() == (
        output / artifacts["score.json"]
    ).read_bytes()
    files_before = {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}
    again = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert again.returncode == 2
    assert "fresh or empty" in again.stderr
    assert all(path.read_bytes() == data for path, data in files_before.items())
