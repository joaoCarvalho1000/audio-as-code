"""Render alternate WAV encodings and an exact excerpt under output/."""

import json
from pathlib import Path

from audio_as_code import render, render_preview
from audio_as_code.demo import demo_song

song = demo_song()
destination = Path("output/production-output")
reports = {
    "pcm24": render(song, destination / "mix-24.wav", wav_format="pcm24"),
    "float32": render(song, destination / "mix-float.wav", wav_format="float32"),
    "preview": render_preview(
        song, destination / "excerpt.wav", start_seconds=2, duration_seconds=3, wav_format="pcm24"
    ),
}
(destination / "reports.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
print(json.dumps(reports, indent=2))
