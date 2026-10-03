"""Run with: uv run python examples/first_light.py"""

import json
from pathlib import Path

from audio_as_code import export_midi, render
from audio_as_code.demo import demo_song

song = demo_song()
output = Path("output")
song.save(output / "first-light.json")
report = render(song, output / "first-light.wav", stems_dir=output / "stems")
export_midi(song, output / "first-light.mid")
(output / "first-light.report.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(report, indent=2))
