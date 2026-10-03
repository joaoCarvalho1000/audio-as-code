"""Repeatable render benchmarks in fresh processes; no audio files are written.

Run ``uv run python examples/benchmark_render.py --help`` for comparison options.
Timing excludes imports, score construction, hashing and memory measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path


def peak_memory_bytes():
    """Process high-water RSS, including imports; not Python-only allocations."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak_working_set",
                    "working_set",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.peak_working_set
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def workload(name):
    from audio_as_code import Note, Song, Track

    if name == "first-light":
        from audio_as_code.demo import demo_song

        return demo_song()
    if name == "full-song":
        from full_compositions import lanterns_on_the_water

        return lanterns_on_the_water()
    if name == "solo":
        return Song(
            title="Benchmark: solo piano",
            beats=16,
            seed=71,
            tracks=[
                Track(
                    name="Piano",
                    instrument="piano",
                    notes=[
                        Note(pitch=pitch, start=index * 4, duration=3.9)
                        for index, pitch in enumerate((48, 60, 69, 76))
                    ],
                )
            ],
        )
    voices = (("piano", 48), ("violin", 67), ("harp", 55), ("marimba", 60))
    return Song(
        title="Benchmark: polyphonic chamber",
        beats=16,
        seed=71,
        tracks=[
            Track(
                name=voice,
                instrument=voice,
                gain=0.3,
                notes=[
                    Note(pitch=pitch + interval, start=beat, duration=3.8)
                    for beat in range(0, 16, 2)
                    for interval in (0, 7)
                    if beat + 3.8 <= 16
                ],
            )
            for voice, pitch in voices
        ],
    )


def worker(args):
    if args.engine_root:
        sys.path.insert(0, str(args.engine_root.resolve()))
    import numpy as np

    import audio_as_code
    from audio_as_code import render_audio

    song = workload(args.workload)
    if args.profile:
        import cProfile

        profiler = cProfile.Profile()
        profiler.enable()
    wall, cpu = time.perf_counter(), time.process_time()
    result = render_audio(song)
    cpu, wall = time.process_time() - cpu, time.perf_counter() - wall
    if args.profile:
        profiler.disable()
        args.profile.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(args.profile))
    peak = peak_memory_bytes()
    print(
        json.dumps(
            {
                "engine": str(Path(audio_as_code.__file__).parent),
                "workload": args.workload,
                "seconds": song.seconds,
                "notes": sum(len(track.notes) for track in song.tracks),
                "wall_seconds": wall,
                "cpu_seconds": cpu,
                "peak_rss_bytes": peak,
                "audio_sha256": hashlib.sha256(result.audio.tobytes()).hexdigest(),
                "sample_rate": song.sample_rate,
                "audio_shape": result.audio.shape,
                "python": platform.python_version(),
                "numpy": np.__version__,
                "platform": platform.platform(),
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workload", choices=("solo", "polyphonic", "first-light", "full-song"), default="solo"
    )
    parser.add_argument(
        "--engine-root", type=Path, help="directory containing an alternate audio_as_code package"
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", type=Path, help="cProfile output (one worker only)")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.worker:
        worker(args)
        return
    rows = []
    for _ in range(1 if args.profile else args.repeats):
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--workload",
            args.workload,
        ]
        if args.engine_root:
            command += ["--engine-root", str(args.engine_root.resolve())]
        if args.profile:
            command += ["--profile", str(args.profile.resolve())]
        rows.append(json.loads(subprocess.check_output(command, text=True, env=os.environ.copy())))
    result = {
        "runs": rows,
        "median": {
            key: statistics.median(row[key] for row in rows)
            for key in ("wall_seconds", "cpu_seconds", "peak_rss_bytes")
        },
        "identical_audio": len({row["audio_sha256"] for row in rows}) == 1,
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
