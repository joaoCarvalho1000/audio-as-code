"""Tempo, moving controls, generated echoes/room, and an audible final release.

Run: uv run python examples/expressive_engine.py
"""

import json
from pathlib import Path

from audio_as_code import (
    Automation,
    Delay,
    Note,
    Reverb,
    Song,
    TempoChange,
    Tone,
    Track,
    export_midi,
    render,
)


def expressive_song() -> Song:
    melody = [
        "E4",
        "G4",
        "B4",
        "D5",
        "B4",
        "G4",
        "A4",
        "F#4",
        "E4",
        "G4",
        "B4",
        "E5",
        "D5",
        "B4",
        "G4",
        "E4",
    ]
    return Song(
        title="After the last beat",
        bpm=112,
        beats=16,
        seed=2026,
        master_gain=0.72,
        tempo_map=[TempoChange(beat=8, bpm=84), TempoChange(beat=12, bpm=126)],
        automation=[
            Automation(
                parameter="master_gain",
                points=[
                    {"beat": 0, "value": 0.58},
                    {"beat": 4, "value": 0.72},
                    {"beat": 12, "value": 0.72},
                    {"beat": 16, "value": 0.6},
                ],
            )
        ],
        effects=[Reverb(decay_seconds=1.8, mix=0.23)],
        tracks=[
            Track(
                name="Moving tines",
                instrument="electric_piano",
                gain=0.6,
                tone=Tone(brightness=0.6),
                release_seconds=0.7,
                automation=[
                    Automation(
                        parameter="pan",
                        points=[
                            {"beat": 0, "value": -0.75},
                            {"beat": 8, "value": 0.75},
                            {"beat": 16, "value": -0.4},
                        ],
                    ),
                    Automation(
                        parameter="gain",
                        points=[
                            {"beat": 0, "value": 0.45},
                            {"beat": 8, "value": 0.7},
                            {"beat": 16, "value": 0.5},
                        ],
                    ),
                ],
                effects=[Delay(time_seconds=0.27, feedback=0.48, repeats=5, mix=0.27)],
                notes=[
                    Note(pitch=pitch, start=i, duration=0.7 if i < 15 else 1)
                    for i, pitch in enumerate(melody)
                ],
            ),
            Track(
                name="Bass",
                instrument="bass_guitar",
                gain=0.44,
                pan=-0.1,
                release_seconds=0.2,
                notes=[
                    Note(pitch=pitch, start=i * 4, duration=3.5, velocity=0.65)
                    for i, pitch in enumerate(["E2", "C3", "A2", "B2"])
                ],
            ),
            Track(
                name="Breath across the change",
                instrument="flute",
                gain=0.24,
                pan=0.3,
                release_seconds=0.45,
                notes=[
                    Note(pitch="B4", start=6, duration=4, velocity=0.6),
                    Note(pitch="G4", start=11, duration=2, velocity=0.6),
                    Note(pitch="E4", start=14, duration=2, velocity=0.6),
                ],
            ),
        ],
    )


def main() -> None:
    song = expressive_song()
    output = Path("output/expressive-engine")
    song.save(output / "score.json")
    report = render(song, output / "after-the-last-beat.wav", stems_dir=output / "stems")
    report["midi"] = export_midi(song, output / "after-the-last-beat.mid")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
