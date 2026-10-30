"""Original loop and depth experiments. Does not record a human listening pass."""

import argparse
import json
import wave
from pathlib import Path

import numpy as np

from audio_as_code import Delay, LoopRegion, Note, Reverb, Song, TempoChange, Track
from audio_as_code._audio import _write_wav
from audio_as_code.arrangement import render_loop_preview, render_periodic_loop
from audio_as_code.experimental_pedal import PedalDepth, render_pedal_depth


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    reports = {}
    for wet in (False, True):
        name = "wet" if wet else "dry"
        song = Song(
            title=f"Periodic {name} study",
            beats=4,
            sample_rate=22050,
            seed=50,
            tempo_map=[TempoChange(beat=2, bpm=90)],
            tracks=[
                Track(
                    name="Pattern",
                    instrument="pad" if wet else "pluck",
                    gain=0.4,
                    release_seconds=0.4 if wet else 0,
                    notes=[
                        Note(pitch=60, duration=0.75),
                        Note(pitch=67, start=3, duration=1 if wet else 0.5),
                    ],
                    effects=[Delay(time_seconds=0.23), Reverb(decay_seconds=0.8)] if wet else [],
                )
            ],
        )
        song.save(output / f"{name}.json")
        result = render_periodic_loop(song, LoopRegion(0, 4))
        frames = result.report["loop"]["cycle_frames"]
        _write_wav(output / f"{name}-cycle.wav", result.audio[:frames], song.sample_rate)
        _write_wav(output / f"{name}-preview.wav", result.audio, song.sample_rate)
        reports[name] = result.report
        with wave.open(str(output / f"{name}-cycle.wav"), "rb") as stream:
            pcm = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2")
            encoded = pcm.reshape(-1, 2).astype(np.float64) / 32768
        window = min(frames, round(0.01 * song.sample_rate))
        nearby = np.concatenate((encoded[-window:], encoded[:window]))
        steps = np.max(np.abs(np.diff(nearby, axis=0)), axis=1)
        reports[name]["encoded_cycle"] = {
            "frames": len(encoded),
            "boundary_jump": float(np.max(np.abs(encoded[0] - encoded[-1]))),
            "nearby_step_percentiles": dict(
                zip(
                    ("p50", "p95", "p99", "max"),
                    (float(v) for v in np.percentile(steps, [50, 95, 99, 100])),
                    strict=True,
                )
            ),
        }
        if not wet:
            reports["dry_crop_reference"] = render_loop_preview(song, LoopRegion(0, 4)).report
    piano = Song(
        title="Repeated-key depth study",
        beats=4,
        sample_rate=22050,
        seed=71,
        tracks=[
            Track(
                name="Piano",
                instrument="piano",
                gain=0.5,
                notes=[
                    Note(pitch=60, duration=0.5, velocity=0.65),
                    Note(pitch=60, start=1, duration=0.5, velocity=0.8),
                    Note(pitch=67, start=2, duration=0.5, velocity=0.5),
                ],
            )
        ],
    )
    piano.save(output / "depth-score.json")
    for name, depth in (("lifted", 0), ("half", 0.5), ("held", 1)):
        result = render_pedal_depth(piano, (PedalDepth(0, 1), PedalDepth(0.75, depth)))
        _write_wav(output / f"depth-{name}.wav", result.audio, piano.sample_rate)
        reports[f"depth-{name}"] = result.report
    reports["listening"] = {
        "status": "not_listened",
        "listener": None,
        "playback_environment": None,
        "dry_join": None,
        "wet_join": None,
        "depth_comparison": None,
    }
    (output / "report.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    generate(parser.parse_args().output)
