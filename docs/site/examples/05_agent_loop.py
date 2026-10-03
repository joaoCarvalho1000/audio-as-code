"""The agent loop, driven only through the `aac` command line and JSON files.

Run from the root of a source checkout:

    python docs/site/examples/05_agent_loop.py [output-directory]

An agent in any language can make the same calls with its shell tool. This
script stands in for that agent: it discovers voices, validates the JSON
score in agent-score.json, renders it, reads the measurements, recovers
from a deliberately invalid edit, applies a measured revision, and checks
that a repeated render is byte-identical. Every candidate gets its own
directory under output/docs-examples/05-agent-loop/.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def aac(*args: str) -> tuple[int, dict]:
    """Run one CLI command. Success: JSON on stdout, exit 0. Failure: JSON on stderr, exit 2."""
    command = [sys.executable, "-m", "audio_as_code", *args]
    done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    print("$ aac", " ".join(args), f"-> exit {done.returncode}")
    return done.returncode, json.loads(done.stdout if done.returncode == 0 else done.stderr)


def write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def candidate(out: Path, name: str, score: dict) -> dict:
    """Validate, render, export MIDI, and measure one score in a fresh directory."""
    folder = out / name
    score_path = write(folder / "score.json", score)
    status, result = aac("validate", str(score_path))
    if status != 0:
        return {"ok": False, "error": result}
    status, report = aac(
        "render",
        str(score_path),
        "-o",
        str(folder / "song.wav"),
        "--report",
        str(folder / "report.json"),
    )
    if status != 0:
        return {"ok": False, "error": report}
    status, midi = aac("midi", str(score_path), "-o", str(folder / "song.mid"))
    if status != 0:
        return {"ok": False, "error": midi}
    status, wav = aac("analyze", str(folder / "song.wav"))
    if status != 0:
        return {"ok": False, "error": wav}
    return {"ok": True, "report": report, "midi": midi, "wav": wav}


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "output/docs-examples/05-agent-loop")
    source = Path(__file__).with_name("agent-score.json")

    # 1. Observe: what can be played, and what shape must the score have?
    _, catalog = aac("instruments")
    playable = {item["id"]: item for item in catalog["instruments"]}
    aac("schema", "-o", str(out / "song-v1.schema.json"))
    print(f"{catalog['counts']['available']} playable voices; policy {catalog['synthesis_policy']}")

    # 2. Compose plain score data; check every instrument and tone field against the catalog.
    score = json.loads(source.read_text(encoding="utf-8"))
    for track in score["tracks"]:
        allowed = playable[track["instrument"]]["tone_controls"]
        assert set(track.get("tone") or {}) <= set(allowed), (track["name"], allowed)

    # 3. Validate, render, and inspect the first draft.
    draft = candidate(out, "v1", score)
    report = draft["report"]
    print("v1 gain_applied:", round(report["gain_applied"], 3), "warnings:", report["warnings"])

    # 4. A bad edit, and recovery from the error's path. This one extends the lead past the end.
    broken = copy.deepcopy(score)
    broken["tracks"][2]["notes"][-1]["duration"] = 8
    failure = candidate(out, "v2-broken", broken)
    issue = failure["error"]["issues"][0]
    print("invalid_score:", issue["message"])
    fixed = copy.deepcopy(broken)
    note = fixed["tracks"][2]["notes"][-1]
    note["duration"] = fixed["beats"] - note["start"]  # end exactly at the song's last beat

    # 5. Revise from the measurements. The draft mix exceeded the 0.95 peak ceiling and was
    #    turned down by the renderer, so lower the master gain by the same amount instead.
    if report["gain_applied"] < 1:
        fixed["master_gain"] = round(fixed["master_gain"] * report["gain_applied"] * 0.9, 3)
    revision = candidate(out, "v2", fixed)
    report2 = revision["report"]
    print("v2 master_gain:", fixed["master_gain"], "gain_applied:", report2["gain_applied"])
    print("v2 warnings:", report2["warnings"] or "none")
    print(f"v2 WAV peak {revision['wav']['peak']:.3f}, rms {revision['wav']['rms']:.4f}")

    # 6. Reproduce: the same score in the same environment renders the same bytes.
    again = candidate(out, "v2-repeat", fixed)
    digests = {
        hashlib.sha256((out / d / "song.wav").read_bytes()).hexdigest() for d in ["v2", "v2-repeat"]
    }
    same = len(digests) == 1
    print("repeat render identical:", same, "| score_sha256", again["report"]["score_sha256"][:16])
    # Measurements are signal checks. Listen to v2/song.wav before calling it finished.


if __name__ == "__main__":
    main()
