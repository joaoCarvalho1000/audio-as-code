"""Production commands preserve one-result JSON and preflight user paths."""

import json
import os

import pytest

from audio_as_code import Note, Song, Track, analyze_wav
from audio_as_code.cli import main


@pytest.fixture
def score(tmp_path):
    path = tmp_path / "score with spaces.json"
    Song(
        sample_rate=22050,
        beats=2,
        tracks=[Track(name="Lead", instrument="sine", notes=[Note(duration=2)])],
    ).save(path)
    return path


@pytest.mark.parametrize("wav_format", ["pcm24", "float32"])
@pytest.mark.parametrize("command", ["render", "preview"])
def test_production_result_and_progress_are_separate(score, tmp_path, capsys, wav_format, command):
    output = tmp_path / "mix.wav"
    progress = tmp_path / "progress.jsonl"
    report = tmp_path / "report.json"
    args = [
        command,
        str(score),
        "-o",
        str(output),
        "--format",
        wav_format,
        "--progress-file",
        str(progress),
        "--report",
        str(report),
    ]
    if command == "preview":
        args.extend(["--start", "0.25", "--duration", "0.5"])
    assert main(args) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result == json.loads(report.read_text())
    assert result["wav"] == analyze_wav(output)
    assert result["wav"]["wav_format"] == wav_format
    if command == "preview":
        # Each endpoint is rounded independently to the nearest sample.
        assert result["wav"]["frames"] == round(0.75 * 22050) - round(0.25 * 22050)
    events = [json.loads(line) for line in progress.read_text().splitlines()]
    assert events and all(event["event"] == "render_progress" for event in events)
    assert all(0 <= event["completed"] <= event["total"] for event in events)


@pytest.mark.parametrize("collision", ["source", "output", "report", "stem", "hardlink"])
def test_progress_path_collisions_preserve_existing_files(score, tmp_path, capsys, collision):
    output = tmp_path / "mix.wav"
    report = tmp_path / "report.json"
    stem = tmp_path / "stems" / "01.wav"
    stem.parent.mkdir()
    for path in (output, report, stem):
        path.write_bytes(b"existing")
    alias = tmp_path / "alias.json"
    os.link(score, alias)
    paths = {"source": score, "output": output, "report": report, "stem": stem, "hardlink": alias}
    before = {path: path.read_bytes() for path in paths.values()}
    assert (
        main(
            [
                "render",
                str(score),
                "-o",
                str(output),
                "--report",
                str(report),
                "--stems",
                str(stem.parent),
                "--progress-file",
                str(paths[collision]),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err)["error"] == "operation_failed"
    assert all(path.read_bytes() == contents for path, contents in before.items())


@pytest.mark.parametrize(
    "options",
    [
        ["--peak-ceiling-dbfs", "-1"],
        ["--target-lufs", "-16", "--no-normalize"],
        ["--target-lufs", "nan"],
        ["--format", "mp3"],
    ],
)
def test_invalid_export_options_do_not_touch_outputs(score, tmp_path, capsys, options):
    output = tmp_path / "mix.wav"
    progress = tmp_path / "progress.jsonl"
    output.write_bytes(b"existing audio")
    progress.write_bytes(b"existing log")
    assert (
        main(
            [
                "render",
                str(score),
                "-o",
                str(output),
                "--progress-file",
                str(progress),
                *options,
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err)["error"] == "operation_failed"
    assert output.read_bytes() == b"existing audio"
    assert progress.read_bytes() == b"existing log"


def test_interrupt_uses_structured_error(score, tmp_path, monkeypatch, capsys):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("audio_as_code.cli.render", interrupted)
    assert main(["render", str(score), "-o", str(tmp_path / "mix.wav")]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err)["message"] == "Operation interrupted"
