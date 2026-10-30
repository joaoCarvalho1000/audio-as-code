"""Reproducible original auditions: uv run python examples/listening_evaluation.py OUTPUT."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

from audio_as_code import Note, Song, Track, render

VOICES = ("piano", "violin", "flute", "marimba", "kick")
RUBRIC = ("onset", "sustain", "release", "recognizability", "artifacts")


def audition_song(voice: str, state: str) -> Song:
    """Six separated original gestures expose three pitches and two velocities."""
    pitches = (60, 69, 76) if voice != "kick" else (36, 38, 40)
    articulation = state if voice in ("violin", "flute") else None
    return Song(
        title=f"Listening evaluation: {voice} {state}",
        bpm=120,
        beats=12,
        sample_rate=22050,
        seed=7301,
        tracks=[
            Track(
                name="Audition",
                instrument=voice,
                gain=0.55,
                articulation=articulation,
                release_seconds=0.2 if state in ("release", "soft") else 0,
                notes=[
                    Note(pitch=pitch, start=index * 2, duration=0.8, velocity=velocity)
                    for index, (pitch, velocity) in enumerate(
                        (p, v) for p in pitches for v in (0.35, 0.85)
                    )
                ],
            )
        ],
    )


def tuning_measurements(song: Song) -> list[dict]:
    """Local spectral peak near nominal f0, not a general pitch/realism estimator."""
    from audio_as_code import render_audio

    audio = render_audio(song).audio.mean(axis=1)
    results = []
    for note in song.tracks[0].notes:
        expected = 440 * 2 ** ((note.pitch - 69) / 12)
        start = round((song.beat_to_seconds(note.start) + 0.08) * song.sample_rate)
        stop = round(song.beat_to_seconds(note.start + note.duration) * song.sample_rate)
        data = audio[start:stop].astype(np.float64)
        spectrum = np.abs(np.fft.rfft(data * np.hanning(len(data)), n=65536))
        frequencies = np.fft.rfftfreq(65536, 1 / song.sample_rate)
        candidates = np.flatnonzero((frequencies > expected * 0.9) & (frequencies < expected * 1.1))
        peak = candidates[np.argmax(spectrum[candidates])]
        pitched = song.tracks[0].instrument != "kick"
        results.append(
            {
                "pitch": note.pitch,
                "velocity": note.velocity,
                "expected_hz": expected if pitched else None,
                "local_peak_hz": float(frequencies[peak]) if pitched else None,
                "local_peak_cents": float(1200 * np.log2(frequencies[peak] / expected))
                if pitched
                else None,
                "method": "hann-window local spectral maximum within 10% of nominal f0"
                if pitched
                else "unpitched drum: tuning not applicable",
            }
        )
    return results


def generate(output: Path, baseline: Path | None = None) -> dict:
    """Never overwrite a baseline or candidate, even when a prior run was interrupted."""
    if baseline is not None:
        baseline = baseline.resolve()
        if output.resolve() == baseline or baseline in output.resolve().parents:
            raise ValueError("candidate must be separate from baseline")
        prior = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))
    else:
        prior = None
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    manifest = {
        "protocol": 1,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "source_commit": commit,
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True
            ).strip()
        ),
        "lock_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "source_hashes": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((root / "src/audio_as_code").rglob("*.py"))
        },
        "protocol_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "render_settings": {"wav_format": "pcm16", "normalize": True, "sample_rate": 22050},
        "clips": {},
        "listening": {},
    }
    for voice in VOICES:
        states = ("soft", "accented") if voice in ("violin", "flute") else ("dry", "release")
        for state in states:
            key = f"{voice}-{state}"
            song = audition_song(voice, state)
            song.save(output / f"{key}.json")
            report = render(song, output / f"{key}.wav")
            (output / f"{key}.report.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            manifest["clips"][key] = {
                "score_sha256": report["score_sha256"],
                "wav_sha256": hashlib.sha256((output / f"{key}.wav").read_bytes()).hexdigest(),
                "measurements": report["wav"],
                "tuning": tuning_measurements(song),
            }
            manifest["listening"][key] = {
                "status": "not_listened",
                "listener": None,
                "playback_environment": None,
                "notes": dict.fromkeys(RUBRIC),
            }
    if prior:
        if set(prior["clips"]) != set(manifest["clips"]):
            raise ValueError("baseline uses a different audition set")
        manifest["baseline_comparison"] = {
            key: {
                "same_score": value["score_sha256"] == prior["clips"][key]["score_sha256"],
                "same_wav": value["wav_sha256"] == prior["clips"][key]["wav_sha256"],
            }
            for key, value in manifest["clips"].items()
        }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    generate(args.output, args.baseline)
    print(json.dumps({"output": str(args.output), "listening": "not_listened"}))
