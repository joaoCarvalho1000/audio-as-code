"""Compare source gestures at matched RMS: uv run python examples/articulations.py."""

from __future__ import annotations

import argparse
import html
import json
import math
import wave
from pathlib import Path

import numpy as np

from audio_as_code import Note, Song, Track, render_audio


def build_comparison(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    measurements = []
    for instrument, pitch in (("violin", 67), ("cello", 48), ("flute", 72), ("trumpet", 60)):
        variants = []
        for articulation in (None, "soft", "accented"):
            label = articulation or "original"
            stem = f"{instrument}-{label}"
            song = Song(
                title=f"{instrument}: {label}",
                beats=6,
                bpm=100,
                sample_rate=22050,
                seed=2026,
                tracks=[
                    Track(
                        name="Phrase",
                        instrument=instrument,
                        articulation=articulation,
                        release_seconds=0.3,
                        notes=[
                            Note(pitch=pitch, start=0, duration=2, velocity=0.7),
                            Note(pitch=pitch + 2, start=2.7, duration=0.6, velocity=0.7),
                            Note(pitch=pitch + 5, start=3.8, duration=0.6, velocity=0.7),
                            Note(pitch=pitch, start=4.9, duration=1.1, velocity=0.7),
                        ],
                    )
                ],
            )
            song.save(output / f"{stem}.json")
            result = render_audio(song, normalize=False)
            audio = result.audio.astype(np.float64)
            rms = float(np.sqrt(np.mean(audio**2)))
            variants.append((stem, label, audio, rms, result.report))

        # One common RMS target per instrument, lowered if any version would
        # exceed the peak ceiling. Gain is fixed over the whole clip, never AGC.
        target = min(
            10 ** (-24 / 20), *(0.9 * rms / np.max(abs(a)) for _, _, a, rms, _ in variants)
        )
        cells = []
        for stem, label, audio, rms, report in variants:
            gain = target / rms
            matched = audio * gain
            pcm = np.rint(matched * 32767).astype("<i2")
            with wave.open(str(output / f"{stem}.wav"), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(22050)
                wav.writeframes(pcm.tobytes())
            measurements.append(
                {
                    "clip": stem,
                    "comparison_gain_db": 20 * math.log10(gain),
                    "matched_rms_dbfs": 20 * math.log10(target),
                    "matched_peak": float(np.max(abs(matched))),
                    "raw_render": report,
                }
            )
            cells.append(
                f"<td><strong>{html.escape(label)}</strong><br>"
                f'<audio controls preload="none" src="{stem}.wav"></audio><br>'
                f'<a href="{stem}.json">Score JSON</a> · '
                f'<a href="{stem}.wav">WAV</a></td>'
            )
        rows.append(f'<tr><th scope="row">{html.escape(instrument)}</th>{"".join(cells)}</tr>')

    (output / "measurements.json").write_text(
        json.dumps(measurements, indent=2) + "\n", encoding="utf-8"
    )
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Source articulation comparison</title><style>"
        "body{font:16px/1.5 system-ui;margin:2rem;max-width:1200px}"
        "td,th{padding:1rem;text-align:left;border-bottom:1px solid #ccc}"
        "audio{width:250px}table{border-collapse:collapse}.scroll{overflow-x:auto}"
        "</style><h1>Source articulation comparison</h1>"
        "<p>Original, soft and accented: the same dry phrase, pitches, velocity, seed "
        "and 300 ms release. WAVs have matched whole-clip RMS per instrument "
        "(normally −24 dBFS), with one constant gain per clip. JSON scores retain "
        "their original gain. RMS matching is not perceptual loudness matching.</p>"
        "<p>Compare the slow first note, two short notes, and the final release. "
        "Soft and accented alter harmonic buildup and colored excitation noise; "
        "their release decays upper harmonics and noise separately. These are "
        "designed source/filter gestures, not a bow-friction or bore simulation.</p>"
        '<div class="scroll"><table><caption>Four instruments, three gestures each</caption>'
        "<thead><tr><th>Instrument</th><th>Original</th><th>Soft</th><th>Accented</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        '<p><a href="measurements.json">Raw render reports and comparison gains</a></p>'
        "</html>",
        encoding="utf-8",
    )
    print(output / "index.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/articulations"))
    build_comparison(parser.parse_args().output)
