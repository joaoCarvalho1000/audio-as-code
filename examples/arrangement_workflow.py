"""Tempo-aware cue, section revision, and dry loop example."""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

from audio_as_code.arrangement import (
    Arrangement,
    LoopRegion,
    Section,
    place_at_seconds,
    render_loop_preview,
)
from audio_as_code.model import Song, TempoChange, Track
from audio_as_code.pattern import Pattern
from audio_as_code.render import render


def cue_song() -> Song:
    # Four beats at 120 BPM, then four at 80 BPM: second 3.5 is beat 6.
    guide = Song(
        title="Timed reveal",
        bpm=120,
        beats=12,
        seed=7,
        tempo_map=(TempoChange(beat=4, bpm=80),),
        tracks=(Track(name="Guide"),),
    )
    reveal = place_at_seconds(guide, Pattern.sequence(["C5"], step=0.5), 3.5)
    bass = Pattern.sequence(["C2", None, "G2", None], gate=0.55).repeat(3)
    return Song.model_validate(
        {
            **guide.model_dump(),
            "tracks": [
                Track(name="Lead", instrument="pluck", notes=reveal).model_dump(),
                Track(name="Bass", instrument="bass", notes=bass.notes).model_dump(),
            ],
        }
    )


def loop_song() -> Song:
    notes = Pattern.sequence(["C4", None, "G4", None], step=1, gate=0.45).notes
    return Song(
        title="Dry four-beat loop",
        bpm=100,
        beats=4,
        seed=7,
        tracks=(Track(name="Loop", instrument="pluck", notes=notes),),
    )


def _write_pcm16(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    samples = np.clip(np.rint(audio * 32768), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(samples.tobytes())


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/arrangement")
    output.mkdir(parents=True, exist_ok=True)
    original = cue_song()
    arrangement = Arrangement(
        original, (Section("opening", 0, 4), Section("reveal", 4, 8), Section("ending", 8, 12))
    )
    # Replace only the lead notes in the reveal section; the bass and score timing stay put.
    revised = arrangement.replace_section(
        "reveal", {"Lead": Pattern.sequence([None, None, "E5", None], gate=0.6)}
    )
    original.save(output / "original.json")
    revised.song.save(output / "revised.json")
    render(revised.song, output / "revised.wav")

    loop = loop_song()
    loop.save(output / "loop.json")
    preview = render_loop_preview(loop, LoopRegion(0, 4), repetitions=2)
    _write_pcm16(output / "two_cycles.wav", preview.audio, loop.sample_rate)
    report = {
        "requested_cue_seconds": 3.5,
        "original_cue_seconds": original.beat_to_seconds(original.tracks[0].notes[0].start),
        "revision_preserved_bass": revised.song.tracks[1] == original.tracks[1],
        "loop": preview.report["loop"],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
