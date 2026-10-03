"""CLI diagnostics and preflight must preserve user files before doing work."""

import json
import os
import subprocess
import sys

import pytest

from audio_as_code import Song, Track, __version__
from audio_as_code.cli import main


def test_version_is_json_and_help_explains_render():
    result = subprocess.run(
        [sys.executable, "-m", "audio_as_code", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"version": __version__}
    assert result.stderr == ""
    help_result = subprocess.run(
        [sys.executable, "-m", "audio_as_code", "render", "--help"],
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0
    assert "300 seconds" in help_result.stdout
    assert "attenuation" in help_result.stdout


@pytest.mark.parametrize("arguments", [[], ["render"], ["validate", "missing-score.json"]])
def test_errors_keep_contract_and_add_recovery_hint(arguments, capsys):
    assert main(arguments) == 2
    captured = capsys.readouterr()
    assert not captured.out
    error = json.loads(captured.err)
    assert error["error"] == "operation_failed"
    assert error["message"] and error["hint"]


@pytest.mark.parametrize(
    "collision", ["hardlink", "report_directory", "parent_file", "nested_output", "stems_file"]
)
def test_render_preflight_preserves_source_and_creates_no_mix(tmp_path, capsys, collision):
    score = tmp_path / "source.json"
    Song(tracks=[Track(name="Lead")]).save(score)
    original = score.read_bytes()
    output = tmp_path / "mix.wav"
    arguments = ["render", str(score), "-o", str(output)]
    if collision == "hardlink":
        alias = tmp_path / "alias.json"
        os.link(score, alias)
        arguments.extend(["--report", str(alias)])
    elif collision == "report_directory":
        arguments.extend(["--report", str(tmp_path)])
    elif collision == "parent_file":
        arguments.extend(["--report", str(score / "report.json")])
    elif collision == "nested_output":
        arguments.extend(["--report", str(output / "report.json")])
    else:
        arguments.extend(["--stems", str(score)])
    assert main(arguments) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "operation_failed"
    assert score.read_bytes() == original
    assert not output.exists()


def test_cli_accepts_utf8_bom_score(tmp_path, capsys):
    score = tmp_path / "score with spaces.json"
    score.write_text('{"tracks": [{"name": "Lead"}]}', encoding="utf-8-sig")
    assert main(["validate", str(score)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"]
