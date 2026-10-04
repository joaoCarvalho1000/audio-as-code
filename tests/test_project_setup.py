"""Scaffolding is useful outside a checkout and must protect existing projects."""

import importlib.metadata
import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from audio_as_code import Song, __version__, analyze_wav, project_setup
from audio_as_code.cli import main


def test_scaffold_composer_runs_from_another_directory_and_matches_initial_score(tmp_path):
    project = tmp_path / "music project with spaces"
    report = project_setup.init_project(project)
    assert set(report["files"]) == {
        "compose.py",
        "score.json",
        "README.md",
        "AGENTS.md",
        "pyproject.toml",
        ".gitignore",
    }
    assert not (project / "output").exists()
    initial = Song.load(project / "score.json")
    namespace = runpy.run_path(str(project / "compose.py"))
    assert namespace["build_song"]() == initial
    assert f'"audio-as-code=={__version__}"' in (project / "pyproject.toml").read_text()
    result = subprocess.run(
        [sys.executable, str(project / "compose.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert not result.stderr
    rendered = json.loads(result.stdout)
    assert rendered["render"]["audio"]["silent"] is False
    assert Song.load(project / "output/score.json") == initial
    assert analyze_wav(project / "output/song.wav")["silent"] is False
    assert (project / "output/song.mid").is_file()
    assert (project / "output/report.json").is_file()
    assert not (tmp_path / "output").exists()


def test_init_accepts_existing_empty_directory(tmp_path):
    project = tmp_path / "empty"
    project.mkdir()
    project_setup.init_project(project)
    assert (project / "compose.py").is_file()


@pytest.mark.parametrize(
    "existing", ["README.md", "uv.lock", ".gitignore", "personal.txt", "child"]
)
def test_nonempty_projects_are_preserved_in_full(tmp_path, existing):
    project = tmp_path / "existing"
    project.mkdir()
    original = project / existing
    if existing == "child":
        original.mkdir()
    else:
        original.write_bytes(b"personal project content")
    with pytest.raises(ValueError, match="must be empty"):
        project_setup.init_project(project)
    assert list(project.iterdir()) == [original]
    if original.is_file():
        assert original.read_bytes() == b"personal project content"
    assert not list(tmp_path.glob(".aac-init-*"))


@pytest.mark.parametrize("blocked_parent", [False, True])
def test_existing_file_and_blocked_parent_leave_user_file_intact(tmp_path, blocked_parent):
    original = tmp_path / "existing"
    original.write_bytes(b"personal content")
    destination = original / "new" if blocked_parent else original
    with pytest.raises(ValueError, match="existing file"):
        project_setup.init_project(destination)
    assert original.read_bytes() == b"personal content"


def test_template_failure_creates_no_directory(tmp_path, monkeypatch):
    def broken_templates():
        raise FileNotFoundError("missing packaged template")

    monkeypatch.setattr(project_setup, "_project_files", broken_templates)
    with pytest.raises(FileNotFoundError):
        project_setup.init_project(tmp_path / "new parent" / "project")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("existing_directory", [False, True])
def test_publish_failure_rolls_back_only_created_project_files(
    tmp_path, monkeypatch, existing_directory
):
    destination = tmp_path / "project"
    if existing_directory:
        destination.mkdir()
    original_read = Path.read_bytes

    def failed_staged_read(path):
        if path.parent.name.startswith(".aac-init-") and path.name == "score.json":
            raise OSError("synthetic publication failure")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", failed_staged_read)
    with pytest.raises(OSError, match="synthetic publication failure"):
        project_setup.init_project(destination)
    assert destination.exists() is existing_directory
    if existing_directory:
        assert list(destination.iterdir()) == []
    assert not list(tmp_path.glob(".aac-init-*"))


def test_exclusive_publication_does_not_replace_a_late_user_file(tmp_path, monkeypatch):
    destination = tmp_path / "project"
    destination.mkdir()
    preflight = project_setup._preflight
    count = 0

    def add_file_after_final_preflight(path):
        nonlocal count
        preflight(path)
        count += 1
        if count == 2:
            (path / "AGENTS.md").write_bytes(b"late user instructions")

    monkeypatch.setattr(project_setup, "_preflight", add_file_after_final_preflight)
    with pytest.raises(FileExistsError):
        project_setup.init_project(destination)
    assert (destination / "AGENTS.md").read_bytes() == b"late user instructions"
    assert [path.name for path in destination.iterdir()] == ["AGENTS.md"]


def test_init_rejects_directory_symlink(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")
    with pytest.raises(ValueError, match="symlink or junction"):
        project_setup.init_project(link)
    assert list(actual.iterdir()) == []


def test_doctor_absent_optional_uv_is_healthy_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = project_setup.doctor()
    assert result["ok"] is True
    assert result["engine_version"] == __version__
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["uv"]["status"] == "warning"
    assert checks["uv"]["hint"]
    assert checks["synthesis"]["status"] == "pass"
    assert 1 <= checks["synthesis"]["frames"] <= 22050
    assert list(tmp_path.iterdir()) == []
    json.dumps(result, allow_nan=False)


def test_doctor_reports_runtime_failure_with_recovery_hint(monkeypatch):
    def fail():
        raise RuntimeError("synthetic synthesis failure")

    monkeypatch.setattr(project_setup, "_runtime_probe", fail)
    result = project_setup.doctor()
    assert result["ok"] is False
    check = next(check for check in result["checks"] if check["name"] == "synthesis")
    assert check["status"] == "error"
    assert "synthetic synthesis failure" in check["message"]
    assert check["hint"]


def test_doctor_reports_missing_dependency_metadata(monkeypatch):
    version = importlib.metadata.version

    def missing(name):
        if name == "mido":
            raise importlib.metadata.PackageNotFoundError(name)
        return version(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    result = project_setup.doctor()
    assert result["ok"] is False
    check = next(check for check in result["checks"] if check["name"] == "mido")
    assert check["status"] == "error"
    assert check["hint"]


@pytest.mark.parametrize("entrypoint", ["module", "console"])
def test_both_entrypoints_scaffold_and_diagnose_outside_checkout(tmp_path, entrypoint):
    if entrypoint == "module":
        command = [sys.executable, "-m", "audio_as_code"]
    else:
        executable = Path(sys.executable).parent / ("aac.exe" if os.name == "nt" else "aac")
        assert executable.is_file()
        command = [str(executable)]
    project = tmp_path / "new music"
    initialized = subprocess.run(
        [*command, "init", str(project)], cwd=tmp_path, capture_output=True, text=True
    )
    assert initialized.returncode == 0, initialized.stderr
    assert not initialized.stderr
    assert "compose.py" in json.loads(initialized.stdout)["files"]
    diagnosed = subprocess.run([*command, "doctor"], cwd=project, capture_output=True, text=True)
    assert diagnosed.returncode == 0, diagnosed.stderr
    assert json.loads(diagnosed.stdout)["ok"] is True
    assert not diagnosed.stderr


@pytest.mark.parametrize("arguments", [["init"], ["init", "--force"], ["doctor", "unexpected"]])
def test_invalid_setup_arguments_use_json_error_contract(arguments, capsys):
    assert main(arguments) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error"] == "operation_failed"
    assert error["hint"]
