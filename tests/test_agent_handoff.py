"""Exercise the documented agent bridge against the installed CLI."""

import json
import subprocess
import sys
from pathlib import Path

from audio_as_code import Note, Song, Track

SCRIPT = Path(__file__).resolve().parents[1] / "docs/site/examples/06_agent_handoff.py"


def run_handoff(score, output):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(score), str(output)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def test_handoff_checks_export_readiness_before_creating_output(tmp_path):
    score = tmp_path / "long.json"
    Song(beats=601, tracks=[Track(name="Long")]).save(score)
    before = score.read_bytes()
    output = tmp_path / "new candidate"
    result = run_handoff(score, output)
    assert result.returncode == 2, result.stderr
    assert result.stdout == ""
    error = json.loads(result.stderr)
    assert error["error"] == "score_not_exportable"
    assert any(issue["code"] == "render_duration_limit" for issue in error["issues"])
    assert not output.exists()
    assert score.read_bytes() == before


def test_handoff_delivers_inspection_and_preserves_existing_candidate(tmp_path):
    score = tmp_path / "short.json"
    Song(beats=1, tracks=[Track(name="Tone", instrument="sine", notes=[Note()])]).save(score)
    output = tmp_path / "candidate with spaces"
    first = run_handoff(score, output)
    assert first.returncode == 0, first.stderr
    handoff = json.loads(first.stdout)
    for key in ("score", "audio", "midi", "report", "analysis", "inspection"):
        assert Path(handoff[key]).is_file()
    inspection = json.loads(Path(handoff["inspection"]).read_text(encoding="utf-8"))
    assert inspection["readiness"]["render"]["ready"]
    assert inspection["readiness"]["midi"]["ready"]
    assert handoff["duration_seconds"] == 0.5
    originals = {path.name: path.read_bytes() for path in output.iterdir()}
    again = run_handoff(score, output)
    assert again.returncode == 1
    assert json.loads(again.stderr)["error"] == "handoff_failed"
    assert {path.name: path.read_bytes() for path in output.iterdir()} == originals
