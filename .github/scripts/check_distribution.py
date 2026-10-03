"""Inspect release artifacts without importing or extracting their contents."""

from __future__ import annotations

import argparse
import ast
import json
import re
import stat
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_PARTS = {
    ".git",
    ".env",
    ".agents",
    ".codex",
    ".impeccable",
    ".wrangler",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "%systemdrive%",
    "output",
    "dist",
    "build",
}
PRIVATE_SUFFIXES = {".pyc", ".pyo", ".log", ".key", ".pem", ".wav", ".mp3", ".mid", ".midi"}
SDIST_ROOTS = {
    "src",
    "tests",
    "examples",
    "docs",
    "schemas",
    "skills",
    "web",
    ".github",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "DESIGN.md",
    "PRODUCT.md",
    "CHANGELOG.md",
    "SECURITY.md",
    ".gitignore",
    "pyproject.toml",
    "uv.lock",
    "PKG-INFO",
}
REQUIRED_SOURCE = {
    "src/audio_as_code/__init__.py",
    "src/audio_as_code/py.typed",
    "src/audio_as_code/extended.py",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "docs/architecture.md",
    "docs/extended-instruments.md",
    "docs/instrument-refinement.md",
    "docs/piano-sustain.md",
    "docs/creative-workflows.md",
    "docs/render-performance.md",
    "docs/cloudflare-hosting.md",
    "docs/releasing.md",
    "schemas/song-v1.schema.json",
    "examples/first_light.py",
    "examples/classic_showcase.py",
    "examples/piano_sustain.py",
    "examples/creative_workflows.py",
    "examples/benchmark_render.py",
    "examples/prepare_cloudflare.py",
    "examples/music/classics-full.json",
    "skills/audio-as-code/SKILL.md",
    ".github/workflows/ci.yml",
    ".github/scripts/check_distribution.py",
    ".github/scripts/smoke_installed.py",
    "web/cloudflare/worker.js",
    "web/cloudflare/media-handler.js",
    "web/cloudflare/package.json",
    "web/cloudflare/package-lock.json",
}


def private_path(name: str) -> bool:
    """Reject private/generated paths at any nesting depth, including Windows spelling."""
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    if normalized.startswith("/") or ".." in parts or any(":" in part for part in parts):
        return True
    for part in parts:
        lower = part.lower()
        if lower in PRIVATE_PARTS or lower.startswith((".env", "credentials")):
            return True
        if lower.endswith(".egg-info") or PurePosixPath(lower).suffix in PRIVATE_SUFFIXES:
            return True
    return False


def source_version(root: Path = ROOT) -> str:
    tree = ast.parse((root / "src/audio_as_code/__init__.py").read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    raise ValueError("No literal __version__ in the package entry point")


def check_metadata(data: bytes, expected_version: str) -> None:
    metadata = BytesParser().parsebytes(data)
    if metadata["Name"] != "audio-as-code" or metadata["Version"] != expected_version:
        raise ValueError("Distribution name/version disagree with the package's __version__")
    if metadata["Requires-Python"] != ">=3.10":
        raise ValueError("Unexpected Python requirement")
    if (metadata["License-Expression"] or metadata["License"]) != "MIT":
        raise ValueError("MIT license metadata is missing")
    requirements = metadata.get_all("Requires-Dist", [])
    names = {re.split(r"[<>=!~;\s\[]", item, maxsplit=1)[0].lower() for item in requirements}
    if names != {"numpy", "pydantic", "mido"} or any("@" in item for item in requirements):
        raise ValueError("Runtime dependencies changed or contain nonportable direct URLs")


def check_wheel(path: Path, expected_version: str) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate wheel members")
        info_root = f"audio_as_code-{expected_version}.dist-info"
        for info in archive.infolist():
            if private_path(info.filename) or PurePosixPath(info.filename).parts[0] not in {
                "audio_as_code",
                info_root,
            }:
                raise ValueError(f"Unexpected wheel member: {info.filename}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Wheel may not contain symlinks: {info.filename}")
        required = {
            f"audio_as_code/{name}"
            for name in (
                "__init__.py",
                "__main__.py",
                "cli.py",
                "model.py",
                "pattern.py",
                "render.py",
                "extended.py",
                "py.typed",
            )
        }
        required |= {f"{info_root}/METADATA", f"{info_root}/WHEEL", f"{info_root}/entry_points.txt"}
        if missing := required - set(names):
            raise ValueError(f"Missing wheel files: {sorted(missing)}")
        if not any(
            name.startswith(info_root + "/") and name.endswith("/LICENSE") for name in names
        ):
            raise ValueError("Wheel is missing the license file")
        check_metadata(archive.read(f"{info_root}/METADATA"), expected_version)
        entry_points = archive.read(f"{info_root}/entry_points.txt").decode()
        if "aac = audio_as_code.cli:main" not in entry_points:
            raise ValueError("Wheel is missing the aac console entry point")
    return {"file": path.name, "files": len(names), "typed": True}


def check_sdist(path: Path, expected_version: str) -> dict:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        prefix = f"audio_as_code-{expected_version}/"
        names = set()
        for member in members:
            if member.isdir():
                continue
            if not member.isfile() or not member.name.startswith(prefix):
                raise ValueError(f"Unexpected sdist member: {member.name}")
            name = member.name[len(prefix) :]
            if private_path(name) or PurePosixPath(name).parts[0] not in SDIST_ROOTS:
                raise ValueError(f"Private/generated or unlisted sdist member: {name}")
            if name in names:
                raise ValueError(f"Duplicate sdist member: {name}")
            names.add(name)
        if missing := REQUIRED_SOURCE - names:
            raise ValueError(f"Missing sdist files: {sorted(missing)}")
        metadata = archive.extractfile(prefix + "PKG-INFO")
        if metadata is None:
            raise ValueError("Missing sdist metadata")
        check_metadata(metadata.read(), expected_version)
    return {"file": path.name, "files": len(names), "portable_source": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    wheels = sorted(args.directory.glob("*.whl"))
    sdists = sorted(args.directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        parser.error("Expected exactly one wheel and one sdist; use a fresh output directory")
    version = source_version()
    try:
        result = {
            "version": version,
            "wheel": check_wheel(wheels[0], version),
            "sdist": check_sdist(sdists[0], version),
        }
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
