"""A first score: four bars, four tracks, one WAV, one MIDI file.

Run from the root of a source checkout:

    python docs/site/examples/01_first_score.py [output-directory]

Writes score.json, song.wav, song.mid, and report.json to
output/docs-examples/01-first-score/ unless another directory is given.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from audio_as_code import Pattern, Song, Track, export_midi, render

out = Path(sys.argv[1] if len(sys.argv) > 1 else "output/docs-examples/01-first-score")

# Time is measured in quarter-note beats. One step of 0.5 is an eighth note.
# None is a rest; a list is a chord; strings and integers are pitches (C4 = 60).
# Two lines of four beats each, written as plain Python lists.
bar_1_2 = ["E4", "G4", "A4", None, "G4", "E4", "D4", None]
bar_3_4 = ["C4", "D4", "E4", "G4", "E4", None, None, None]
melody = Pattern.sequence(
    bar_1_2 + bar_3_4,
    step=0.5,
    gate=0.75,
    velocity=0.7,
)
chords = Pattern.sequence(
    [["C3", "E3", "G3"], ["A2", "C3", "E3"], ["F2", "A2", "C3"], ["G2", "B2", "D3"]],
    step=4,
    gate=0.95,
    velocity=0.5,
)
kick = Pattern.sequence([36, None, 36, None], gate=0.4, velocity=0.9).repeat(4)
hat = Pattern.sequence([None, 42], step=0.5, gate=0.2, velocity=0.45).repeat(16)

song = Song(
    title="First score",
    bpm=96,  # 96 quarter notes per minute, so 16 beats last 10 seconds
    beats=16,  # four bars of 4/4; every note must end by beat 16
    seed=1,
    tracks=[
        # The melody pattern is 8 beats long; .repeat(2) fills all four bars.
        Track(name="Melody", instrument="pluck", gain=0.55, pan=0.2, notes=melody.repeat(2).notes),
        Track(name="Chords", instrument="pad", gain=0.3, pan=-0.2, notes=chords.notes),
        Track(name="Kick", instrument="kick", gain=0.8, notes=kick.notes),
        Track(name="Hat", instrument="hat", gain=0.3, pan=0.3, notes=hat.notes),
    ],
)

song.save(out / "score.json")
report = render(song, out / "song.wav")
midi = export_midi(song, out / "song.mid")
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

digest = hashlib.sha256((out / "song.wav").read_bytes()).hexdigest()
print(f"{song.title}: {song.beats} beats at {song.bpm} BPM = {song.seconds:.2f} s")
print(f"WAV  {report['output']}  peak {report['wav']['peak']:.3f}  sha256 {digest[:16]}...")
print(f"MIDI {midi['output']}  {midi['duration_seconds']:.2f} s")
print("warnings:", report["warnings"] or "none")
