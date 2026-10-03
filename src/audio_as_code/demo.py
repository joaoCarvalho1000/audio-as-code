"""A small, original arrangement generated entirely from the public score API."""

from .model import Song, Track
from .pattern import Pattern


def demo_song() -> Song:
    # Eight bars: Am7 / Fmaj7 / Cmaj7 / G, then a melodic variation.
    chords = [
        ["A3", "C4", "E4", "G4"],
        ["F3", "A3", "C4", "E4"],
        ["C3", "E3", "G3", "B3"],
        ["G3", "B3", "D4", "G4"],
    ]
    pads = Pattern.sequence(chords, step=4, gate=0.95, velocity=0.55).repeat(2)
    bass = Pattern.sequence(
        [
            "A2",
            None,
            "E3",
            "A2",
            "F2",
            None,
            "C3",
            "F2",
            "C2",
            None,
            "G2",
            "C3",
            "G2",
            None,
            "D3",
            "G2",
        ],
        gate=0.72,
        velocity=0.8,
    ).repeat(2)
    melody = Pattern.sequence(
        [
            "E5",
            None,
            "C5",
            "B4",
            "A4",
            None,
            "C5",
            "E5",
            "A4",
            "G4",
            None,
            "E4",
            "G4",
            None,
            "B4",
            "D5",
        ],
        step=0.5,
        gate=0.65,
        velocity=0.7,
    )
    variation = Pattern.sequence(
        [
            "E5",
            "G5",
            None,
            "E5",
            "C5",
            "B4",
            "A4",
            None,
            "G4",
            None,
            "A4",
            "B4",
            "D5",
            "B4",
            "G4",
            None,
        ],
        step=0.5,
        gate=0.7,
        velocity=0.74,
    )
    kick = Pattern.sequence([36, None, 36, None], gate=0.4, velocity=0.9).repeat(8)
    snare = Pattern.sequence([None, 38, None, 38], gate=0.28, velocity=0.7).repeat(8)
    hat = Pattern.sequence([42, 42, 42, 42], step=0.5, gate=0.16, velocity=0.45).repeat(16)
    return Song(
        title="First Light",
        bpm=104,
        beats=32,
        seed=7,
        tracks=(
            Track(name="Warm chords", instrument="pad", gain=0.34, pan=-0.25, notes=pads.notes),
            Track(name="Bass", instrument="bass", gain=0.65, notes=bass.notes),
            Track(
                name="Melody",
                instrument="pluck",
                gain=0.52,
                pan=0.3,
                notes=melody.at(8) + variation.at(24),
            ),
            Track(name="Kick", instrument="kick", gain=0.85, notes=kick.notes),
            Track(name="Snare", instrument="snare", gain=0.48, pan=-0.08, notes=snare.notes),
            Track(name="Hi-hat", instrument="hat", gain=0.34, pan=0.35, notes=hat.notes),
        ),
    )
