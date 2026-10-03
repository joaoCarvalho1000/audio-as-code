"""Compose a short layered phrase: uv run python examples/composition_tools.py."""

import json
from pathlib import Path

from audio_as_code import Pattern, Song, Track, export_midi, render


def composition_song() -> Song:
    motif = Pattern.sequence(
        ["C4", "E4", None, "G4", "E4", None, "D4", None],
        step=0.5,
        gate=0.7,
        velocity=0.65,
    )
    # Double-speed answer, an octave higher and quieter; both end at beat 4.
    answer = motif.transpose(12).stretch(0.5).scale_velocity(0.6)
    phrase = motif.overlay(answer, offset=2)
    melody = motif.then(phrase).then(phrase.scale_velocity(1.15)).then(motif)
    bass = Pattern.sequence(["C2", None, "G2", None], gate=0.7, velocity=0.5).repeat(4)
    return Song(
        title="A small conversation",
        bpm=116,
        beats=melody.beats,
        seed=42,
        tracks=(
            Track(name="Plucked conversation", instrument="pluck", notes=melody.at(0), gain=0.5),
            Track(name="Bass", instrument="bass", notes=bass.at(0), gain=0.4),
        ),
    )


def main() -> None:
    song = composition_song()
    output = Path("output/composition-tools")
    song.save(output / "song.json")
    export_midi(song, output / "song.mid")
    report = render(song, output / "song.wav")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
