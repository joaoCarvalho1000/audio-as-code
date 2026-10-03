"""Tone controls, velocity, gain, pan, and the generated drum kit.

Run from the root of a source checkout:

    python docs/site/examples/04_expressive_controls.py [output-directory]

Each instrument accepts only the Tone fields listed in its catalog entry
(`aac instruments`). Tone applies to a whole track, so two articulations
of one instrument are two tracks. Writes score.json, song.wav, song.mid,
stems/, and report.json to output/docs-examples/04-expressive-controls/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from audio_as_code import Note, Pattern, Song, Tone, Track, export_midi, get_instrument, render

out = Path(sys.argv[1] if len(sys.argv) > 1 else "output/docs-examples/04-expressive-controls")

# Read the capabilities instead of guessing them.
for voice in ["guitar", "violin", "flute", "theremin", "synthesizer", "pluck"]:
    info = get_instrument(voice)
    print(f"{voice:>11}: tone controls {list(info.tone_controls) or 'none'}")

# Unsupported controls are rejected, never silently ignored.
try:
    Track(name="Bad", instrument="violin", tone=Tone(decay_seconds=3))
except ValidationError as error:
    print("rejected:", error.errors()[0]["msg"])

# Velocity (0-1] changes loudness and, on modeled voices, brightness.
crescendo = [
    Note(pitch=p, start=i * 0.5, duration=0.45, velocity=0.25 + i * 0.06)
    for i, p in enumerate(["E3", "G3", "B3", "E4", "G4", "B4", "E4", "B3"] * 1)
]
guitar_notes = tuple(crescendo) + tuple(
    Note(pitch=p, start=4, duration=4, velocity=0.7) for p in ["E2", "B2", "E3", "G3", "B3"]
)

song = Song(
    title="Expressive controls",
    bpm=80,
    beats=16,
    seed=4,
    master_gain=0.8,
    tracks=[
        # Plucking near the bridge (0.08) is brighter and thinner than mid-string (0.4).
        Track(
            name="Guitar near bridge",
            instrument="guitar",
            pan=-0.45,
            gain=0.55,
            tone=Tone(brightness=0.7, decay_seconds=2.5, pluck_position=0.08),
            notes=guitar_notes,
        ),
        Track(
            name="Guitar mid string",
            instrument="guitar",
            pan=0.45,
            gain=0.55,
            tone=Tone(brightness=0.35, decay_seconds=4, pluck_position=0.4),
            notes=tuple(Note(**{**n.model_dump(), "start": n.start + 8}) for n in guitar_notes),
        ),
        # Wide, slow vibrato on violin; vibrato needs a nonzero depth to be audible.
        Track(
            name="Violin",
            instrument="violin",
            pan=0.2,
            gain=0.4,
            tone=Tone(brightness=0.55, vibrato_depth_cents=25, vibrato_rate_hz=4.5),
            notes=(Note(pitch="B4", start=8, duration=3.8), Note(pitch="G5", start=12, duration=4)),
        ),
        # Breath adds generated air noise to winds.
        Track(
            name="Breathy flute",
            instrument="flute",
            pan=-0.2,
            gain=0.4,
            tone=Tone(breath=0.8, vibrato_depth_cents=8, vibrato_rate_hz=5),
            notes=(Note(pitch="E5", start=0, duration=3.8, velocity=0.6),),
        ),
        # Glide starts each note 7 semitones below and settles onto the written pitch.
        Track(
            name="Theremin",
            instrument="theremin",
            gain=0.3,
            tone=Tone(glide_semitones=-7, vibrato_depth_cents=30, vibrato_rate_hz=6),
            notes=(Note(pitch="E5", start=4, duration=3.5, velocity=0.6),),
        ),
        Track(
            name="Detuned synth",
            instrument="synthesizer",
            pan=0.3,
            gain=0.22,
            tone=Tone(brightness=0.6, detune_cents=25),
            notes=Pattern.sequence([["E3", "B3", "E4"], None], step=2, gate=0.9).repeat(4).at(0),
        ),
        # drum_machine picks a generated voice from the pitch: 36 kick, 38 snare,
        # 42 hat, 45 tom, 49 cymbal, 54 tambourine, 60 bongo, 64 conga.
        Track(
            name="Kit",
            instrument="drum_machine",
            gain=0.5,
            notes=Pattern.sequence(
                [36, 42, 38, 42, 36, [36, 54], 38, 64], step=0.5, gate=0.3, velocity=0.7
            )
            .repeat(4)
            .at(0)
            + (Note(pitch=49, start=15, duration=1, velocity=0.6),),
        ),
    ],
)

song.save(out / "score.json")
report = render(song, out / "song.wav", stems_dir=out / "stems")
midi = export_midi(song, out / "song.mid")
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
for stem in report["stems"]:
    print(f"stem {stem['path']}: {stem['track']}, rms {stem['audio']['rms']:.4f}")
print(f"mix peak {report['wav']['peak']:.3f}; warnings: {report['warnings'] or 'none'}")
print("MIDI note:", midi["warnings"][0])
