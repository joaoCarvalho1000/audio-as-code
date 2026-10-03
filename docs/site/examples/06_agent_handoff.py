"""Validate/render an agent-written score and emit a local artifact handoff.

Run from an installed Audio as Code environment:
    python docs/site/examples/06_agent_handoff.py SCORE.json OUTPUT_DIRECTORY

The output directory must be new. This uses only the Python standard library;
the child CLI uses the Audio as Code installation in the same environment.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


class CLIError(Exception):
    def __init__(self, diagnostic: dict):
        self.diagnostic = diagnostic
        super().__init__(str(diagnostic))


def aac(*arguments: str, timeout: int = 300) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "audio_as_code", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=timeout,
    )
    if result.returncode == 0:
        return json.loads(result.stdout)
    if result.returncode == 2:
        raise CLIError(json.loads(result.stderr))
    raise RuntimeError(f"CLI exited {result.returncode}: {result.stderr}")


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    try:
        inspection = aac("inspect", str(args.score), timeout=60)
        if not all(inspection["readiness"][target]["ready"] for target in ("render", "midi")):
            raise CLIError(
                {
                    "error": "score_not_exportable",
                    "issues": [i for i in inspection["issues"] if i["severity"] == "error"],
                    "hint": "Revise the score so both WAV and MIDI checks pass, then try again.",
                }
            )
        out = args.output_directory.resolve()
        out.mkdir(parents=True, exist_ok=False)
        score = out / "score.json"
        shutil.copyfile(args.score, score)
        write_json(out / "inspection.json", inspection)
        wav, midi, report = out / "song.wav", out / "song.mid", out / "report.json"
        rendered = aac("render", str(score), "-o", str(wav), "--report", str(report))
        analysis = aac("analyze", str(wav), timeout=60)
        exported = aac("midi", str(score), "-o", str(midi), timeout=60)
        write_json(out / "analysis.json", analysis)
        handoff = {
            "score": str(score),
            "audio": str(wav),
            "midi": str(midi),
            "report": str(report),
            "analysis": str(out / "analysis.json"),
            "inspection": str(out / "inspection.json"),
            "duration_seconds": analysis["duration_seconds"],
            "render_warnings": rendered["warnings"],
            "midi_warnings": exported["warnings"],
        }
        write_json(out / "handoff.json", handoff)
        print(json.dumps(handoff, indent=2))
        return 0
    except CLIError as error:
        print(json.dumps(error.diagnostic), file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": "handoff_failed", "message": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
