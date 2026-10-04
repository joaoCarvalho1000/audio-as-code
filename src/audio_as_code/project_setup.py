"""Local project scaffolding and bounded runtime diagnostics, including installed wheels."""

from __future__ import annotations

import importlib
import shutil
import stat
import sys
import tempfile
from importlib import metadata, resources
from pathlib import Path

from .model import Note, Song, Track

_TEMPLATES = {
    "compose.py": "compose.py.txt",
    "score.json": "score.json",
    "README.md": "README.md.txt",
    "AGENTS.md": "AGENTS.md.txt",
    "pyproject.toml": "pyproject.toml.txt",
    ".gitignore": "gitignore.txt",
}


def _project_files() -> dict[str, str]:
    from . import __version__

    templates = resources.files("audio_as_code").joinpath("_project_templates")
    contents = {
        name: templates.joinpath(template)
        .read_text(encoding="utf-8")
        .replace("__AAC_VERSION__", __version__)
        for name, template in _TEMPLATES.items()
    }
    # A missing/corrupt packaged template must fail before any project files exist.
    Song.model_validate_json(contents["score.json"])
    compile(contents["compose.py"], "compose.py", "exec")
    return contents


def _preflight(destination: Path) -> None:
    if destination.is_symlink() or (
        destination.exists()
        and getattr(destination.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    ):
        raise ValueError("project directory must not be a symlink or junction")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError("project path is an existing file; choose a new or empty directory")
        if any(destination.iterdir()):
            raise ValueError(
                "project directory must be empty; existing project files are preserved"
            )
    for parent in destination.parents:
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"project directory is blocked by an existing file: {parent}")


def init_project(path: str | Path) -> dict:
    """Create an editable starter project in an absent or empty directory.

    No installation, rendering, network access or global configuration occurs.
    Writes are staged and published exclusively; known existing files are never replaced.
    """
    destination = Path(path).absolute()
    _preflight(destination)
    contents = _project_files()
    destination.parent.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    made_directory = False
    with tempfile.TemporaryDirectory(prefix=".aac-init-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        for name, text in contents.items():
            (stage / name).write_text(text, encoding="utf-8", newline="\n")
        # Recheck after staging. Exclusive creation also protects a colliding file
        # that appears between this check and its individual write.
        _preflight(destination)
        try:
            if not destination.exists():
                destination.mkdir()
                made_directory = True
            for name in contents:
                target = destination / name
                with target.open("xb") as stream:
                    created.append(target)
                    stream.write((stage / name).read_bytes())
        except BaseException:
            for target in reversed(created):
                target.unlink(missing_ok=True)
            if made_directory:
                try:
                    destination.rmdir()
                except OSError:
                    pass  # A file added by someone else must remain untouched.
            raise
    return {
        "output": str(destination),
        "files": list(contents),
        "next_steps": [
            "Open the project directory and read README.md and AGENTS.md.",
            "With Audio as Code already installed: python -m audio_as_code doctor",
            "With Audio as Code already installed: python compose.py",
            "For a separate project environment: uv sync, then uv run python compose.py",
        ],
    }


def _runtime_probe() -> dict:
    from .render import render_audio

    song = Song(
        beats=0.125,
        sample_rate=22050,
        tracks=[Track(name="Doctor", instrument="pluck", notes=[Note(duration=0.125)])],
    )
    result = render_audio(song)
    measurements = result.report["audio"]
    if measurements["silent"] or measurements["frames"] < 1:
        raise ValueError("the short synthesis check did not produce audible sample values")
    return {"frames": measurements["frames"], "sample_rate": measurements["sample_rate"]}


def doctor() -> dict:
    """Check this imported runtime without installing tools or writing audio.

    The CLI itself needs core dependencies to import. This check can diagnose a
    loaded but failing runtime; it cannot repair a package that fails to import.
    """
    from . import __version__

    checks = []
    python_ok = sys.version_info >= (3, 10)
    checks.append(
        {
            "name": "python",
            "status": "pass" if python_ok else "error",
            "message": f"Python {sys.version.split()[0]}",
            "hint": "Use Python 3.10 or newer in the project's virtual environment.",
        }
    )
    for name in ("numpy", "pydantic", "mido"):
        try:
            importlib.import_module(name)
            installed_version = metadata.version(name)
        except Exception as error:
            checks.append(
                {
                    "name": name,
                    "status": "error",
                    "message": f"Dependency check failed: {type(error).__name__}: {error}",
                    "hint": "Reinstall Audio as Code in this virtual environment, or run uv sync.",
                }
            )
        else:
            checks.append({"name": name, "status": "pass", "message": installed_version})
    try:
        probe = _runtime_probe()
    except Exception as error:
        checks.append(
            {
                "name": "synthesis",
                "status": "error",
                "message": f"Short render failed: {type(error).__name__}: {error}",
                "hint": "Reinstall the environment; if it still fails, report this diagnostic.",
            }
        )
    else:
        checks.append(
            {"name": "synthesis", "status": "pass", "message": "Short in-memory render", **probe}
        )
    uv_available = shutil.which("uv") is not None
    checks.append(
        {
            "name": "uv",
            "status": "pass" if uv_available else "warning",
            "message": "uv is available" if uv_available else "Optional uv command is absent",
            "hint": "uv is optional; README.md also gives a Python venv and pip setup.",
        }
    )
    return {
        "ok": all(check["status"] != "error" for check in checks),
        "engine_version": __version__,
        "python_executable": sys.executable,
        "checks": checks,
    }
