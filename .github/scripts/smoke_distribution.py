"""Rebuild the sdist and smoke-test both wheels in isolated installed environments."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from check_distribution import check_wheel, source_version


def payload(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("audio_as_code/")
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    wheels = list(args.directory.glob("*.whl"))
    sdists = list(args.directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        parser.error("Expected exactly one wheel and one sdist")
    uv = shutil.which("uv")
    if uv is None:
        parser.error("Install uv to run the isolated distribution checks")
    script = Path(__file__).with_name("smoke_installed.py").resolve()
    with tempfile.TemporaryDirectory(prefix="aac-distribution-") as folder:
        work = Path(folder)
        subprocess.run(
            [
                uv,
                "build",
                str(sdists[0].resolve()),
                "--wheel",
                "--no-sources",
                "--out-dir",
                str(work / "rebuilt"),
                "--python",
                sys.executable,
            ],
            check=True,
            cwd=work,
        )
        rebuilt = next((work / "rebuilt").glob("*.whl"))
        check_wheel(rebuilt, source_version())
        assert payload(wheels[0]) == payload(rebuilt), "Sdist rebuild changed the installed package"
        for wheel in (wheels[0].resolve(), rebuilt):
            subprocess.run(
                [
                    uv,
                    "run",
                    "--isolated",
                    "--no-project",
                    "--python",
                    sys.executable,
                    "--with",
                    str(wheel),
                    "python",
                    "-I",
                    str(script),
                ],
                check=True,
                cwd=work,
            )
    print(json.dumps({"sdist_rebuild": "passed", "isolated_wheel_installs": 2}))


if __name__ == "__main__":
    main()
