"""Regressions for private-file leaks and broken installed distribution metadata."""

import importlib.util
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "distribution_check", ROOT / ".github/scripts/check_distribution.py"
)
assert SPEC is not None and SPEC.loader is not None
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


@pytest.mark.parametrize(
    "name",
    [
        "src/audio_as_code/.env.production",
        "docs/.codex/session.json",
        "examples/.agents/memory.md",
        "web/.impeccable/review/report.md",
        "web/.wrangler/state/cache.json",
        "web/.dev.vars",
        "examples/.dev.vars.production",
        "docs/.claude/session.json",
        ".internal/plan.md",
        "docs/internal/decision.md",
        "web/site/DESIGN.md",
        "PRODUCT.md",
        "docs/instrument-browser-brief.md",
        "docs/instrument-refinement.md",
        "HANDOFF.md",
        "tests/.hypothesis/state.json",
        "tests/test-results/report.html",
        "examples/profile.prof",
        "web/certificate.pfx",
        "examples/output/render.wav",
        "src/audio_as_code/__pycache__/model.pyc",
        "docs/debug.log",
        "examples/credentials.json",
        "examples/private.key",
        "%SystemDrive%/ProgramData/cache.db",
        "docs\\.env.local",
        "../outside.txt",
        "/absolute.txt",
        "C:/private.txt",
    ],
)
def test_private_or_unsafe_archive_members_are_rejected(name):
    assert CHECK.private_path(name)


@pytest.mark.parametrize(
    "name",
    [
        ".github/workflows/ci.yml",
        "src/audio_as_code/py.typed",
        "examples/music/classics-full.json",
        "examples/music/classics-sources/ode_to_joy-ode_to_joy.ly",
        "docs/releasing.md",
        "AGENTS.md",
        "skills/audio-as-code/SKILL.md",
        "web/site/assets/fonts/Archivo-OFL.txt",
    ],
)
def test_portable_source_members_are_allowed(name):
    assert not CHECK.private_path(name)


def test_gitignore_excludes_local_state_but_keeps_agent_and_license_docs(tmp_path):
    git = shutil.which("git")
    if git is None:
        pytest.skip("Git is needed to exercise ignore rules")
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True)
    shutil.copyfile(ROOT / ".gitignore", tmp_path / ".gitignore")
    private = [
        "DESIGN.md",
        "web/site/DESIGN.md",
        "PRODUCT.md",
        "HANDOFF.md",
        "docs/instrument-browser-brief.md",
        "docs/instrument-refinement.md",
        "docs/internal/decision.md",
        ".internal/plan.md",
        ".claude/session.json",
        "web/.dev.vars",
        "web/.dev.vars.production",
        "tests/.hypothesis/state.json",
        "web/.wrangler/state.json",
        "tests/test-results/report.html",
        "output/render.wav",
    ]
    public = ["README.md", "AGENTS.md", "skills/audio-as-code/SKILL.md", "docs/synthesis.md"]
    result = subprocess.run(
        [git, "-C", str(tmp_path), "check-ignore", "-z", "--stdin"],
        input=("\0".join(private + public) + "\0").encode(),
        capture_output=True,
        check=True,
    )
    assert set(result.stdout.decode().rstrip("\0").split("\0")) == set(private)


def test_source_zip_excludes_internal_files_that_still_exist_locally(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("site_archive", ROOT / "examples/build_site.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    checkout = tmp_path / "checkout"
    public = ["README.md", "AGENTS.md", "docs/synthesis.md", "skills/audio-as-code/SKILL.md"]
    private = [
        "DESIGN.md",
        "PRODUCT.md",
        "web/site/DESIGN.md",
        "docs/instrument-browser-brief.md",
        "docs/instrument-refinement.md",
        "docs/internal/notes.md",
        "web/.dev.vars",
        "web/.claude/settings.json",
        "examples/HANDOFF.md",
        "examples/profile.prof",
        "tests/test-results/report.html",
        "web/.wrangler/state.json",
    ]
    for name in public + private:
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic boundary fixture", encoding="utf-8")
    monkeypatch.setattr(builder, "ROOT", checkout)
    site = builder.Site(tmp_path / "published")
    report = site.source_archive()
    with zipfile.ZipFile(site.out / report["file"]) as archive:
        assert archive.testzip() is None
        assert {name.removeprefix("audio-as-code/") for name in archive.namelist()} == set(public)


def wheel(tmp_path, *, extra=None, omit=None, version="0.1.0"):
    files = {
        f"audio_as_code/{name}": ""
        for name in (
            "__init__.py",
            "__main__.py",
            "cli.py",
            "model.py",
            "pattern.py",
            "render.py",
            "extended.py",
            "_audio.py",
            "_voices.py",
            "_export_rules.py",
            "_orchestra_profiles.py",
            "py.typed",
        )
    }
    info = f"audio_as_code-{version}.dist-info"
    files.update(
        {
            f"{info}/METADATA": (
                f"Metadata-Version: 2.4\nName: audio-as-code\nVersion: {version}\n"
                "Requires-Python: >=3.10\nLicense-Expression: MIT\n"
                "Requires-Dist: numpy<3,>=1.24\nRequires-Dist: pydantic<3,>=2.7\n"
                "Requires-Dist: mido<2,>=1.3\n"
            ),
            f"{info}/WHEEL": "Wheel-Version: 1.0\n",
            f"{info}/entry_points.txt": "[console_scripts]\naac = audio_as_code.cli:main\n",
            f"{info}/licenses/LICENSE": "MIT License\n",
        }
    )
    if extra:
        files.update(extra)
    if omit:
        files.pop(omit)
    path = tmp_path / "example.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def test_wheel_checker_requires_type_marker_and_rejects_nested_private_state(tmp_path):
    assert CHECK.check_wheel(wheel(tmp_path), "0.1.0")["typed"]
    with pytest.raises(ValueError, match="Missing wheel files"):
        CHECK.check_wheel(wheel(tmp_path, omit="audio_as_code/py.typed"), "0.1.0")
    with pytest.raises(ValueError, match="Unexpected wheel member"):
        CHECK.check_wheel(wheel(tmp_path, extra={"audio_as_code/.env": "test-secret"}), "0.1.0")


@pytest.mark.parametrize("module", ["_audio", "_voices", "_export_rules", "_orchestra_profiles"])
def test_wheel_requires_internal_modules_used_by_public_imports(tmp_path, module):
    with pytest.raises(ValueError, match="Missing wheel files"):
        CHECK.check_wheel(wheel(tmp_path, omit=f"audio_as_code/{module}.py"), "0.1.0")


def test_wheel_checker_detects_version_and_entry_point_drift(tmp_path):
    with pytest.raises(ValueError, match="Unexpected wheel member"):
        CHECK.check_wheel(wheel(tmp_path, version="0.2.0"), "0.1.0")
    with pytest.raises(ValueError, match="console entry point"):
        CHECK.check_wheel(
            wheel(tmp_path, extra={"audio_as_code-0.1.0.dist-info/entry_points.txt": ""}), "0.1.0"
        )
