"""Original swung groove. Run: uv run python examples/rhythm_sketch.py"""

import json
from pathlib import Path

from audio_as_code import Pattern, Song, Track, export_midi, render


def make_song() -> Song:
    motif = Pattern.sequence(
        ["D4", None, "F4", "A4", None, "E4", "C4", None], step=0.5, velocity=0.65
    )
    melody = motif.then(motif.reverse().scale_velocity(0.8)).swing(0.6).repeat(2)
    kick = Pattern.euclidean(4, 8, pitch=36, gate=0.25, velocity=0.7).repeat(4)
    hats = (
        Pattern.euclidean(5, 8, pitch=42, rotation=1, gate=0.2, velocity=0.35).swing(0.6).repeat(4)
    )
    bass = Pattern.sequence(["D2", None, "A2", None], gate=0.7, velocity=0.55).repeat(4)
    return Song(
        title="Pocket sketches",
        bpm=108,
        beats=16,
        tracks=(
            Track(name="Melody", instrument="marimba", notes=melody.at(0)),
            Track(name="Bass", instrument="pluck", notes=bass.at(0)),
            Track(name="Kick", instrument="kick", gain=0.7, notes=kick.at(0)),
            Track(name="Hats", instrument="hat", gain=0.4, pan=0.25, notes=hats.at(0)),
        ),
    )


def main() -> None:
    output = Path("output/rhythm-sketch")
    song = make_song()
    song.save(output / "score.json")
    report = render(song, output / "song.wav")
    export_midi(song, output / "song.mid")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
