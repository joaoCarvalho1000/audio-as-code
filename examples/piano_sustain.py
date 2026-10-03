"""Original A/B piano phrase: uv run python examples/piano_sustain.py."""

import argparse
import json
from pathlib import Path

from audio_as_code import (
    Note,
    PedalEvent,
    Song,
    TempoChange,
    Tone,
    Track,
    export_midi,
    inspect_score,
    render,
)


def sustain_song(*, pedal: bool) -> Song:
    """The same key gestures with or without a damper pedal; no borrowed melody."""
    notes = [
        Note(pitch=pitch, start=start, duration=duration, velocity=velocity)
        for pitch, start, duration, velocity in [
            ("C3", 0, 0.75, 0.72),
            ("E4", 0.5, 0.4, 0.65),
            ("G4", 1, 0.4, 0.70),
            ("E4", 1.5, 0.4, 0.58),
            ("F3", 2.5, 0.5, 0.68),
            ("A4", 3, 0.4, 0.66),
            ("C5", 3.5, 0.4, 0.61),
            ("G3", 4.5, 0.5, 0.69),
            ("D4", 5, 0.4, 0.60),
            ("G4", 5.5, 0.4, 0.64),
            ("C3", 6.5, 0.5, 0.65),
            ("E4", 6.75, 0.5, 0.57),
            ("G4", 7, 0.5, 0.54),
        ]
    ]
    events = [
        PedalEvent(beat=0, down=True),
        PedalEvent(beat=2.25, down=False),
        PedalEvent(beat=2.5, down=True),
        PedalEvent(beat=4.25, down=False),
        PedalEvent(beat=4.5, down=True),
        PedalEvent(beat=6.25, down=False),
        PedalEvent(beat=6.5, down=True),
    ]
    return Song(
        title="Open Windows — piano pedal A/B",
        beats=8,
        bpm=100,
        seed=203,
        tempo_map=[TempoChange(beat=6, bpm=80)],
        tracks=[
            Track(
                name="Piano",
                instrument="piano",
                gain=0.65,
                tone=Tone(brightness=0.55, decay_seconds=5),
                notes=notes,
                pedal=events if pedal else [],
            )
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/piano-sustain"))
    output = parser.parse_args().output
    reports = {}
    for name, enabled in [("dry", False), ("pedal", True)]:
        song = sustain_song(pedal=enabled)
        song.save(output / f"{name}.json")
        reports[name] = {
            "render": render(song, output / f"{name}.wav"),
            "midi": export_midi(song, output / f"{name}.mid"),
            "inspection": inspect_score(song),
        }
    reports["audition"] = "Not auditioned by this script; reports contain numerical checks only."
    (output / "report.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "reports": str(output / "report.json")}, indent=2))


if __name__ == "__main__":
    main()
