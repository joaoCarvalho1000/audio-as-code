"""Hear generated instrument models: uv run python examples/physical_instruments.py."""

from __future__ import annotations

import json
from pathlib import Path

from showcase import write_gallery

from audio_as_code import Note, Song, Tone, Track, export_midi, midi_pitch, render


def guitar_phrase(instrument="guitar") -> Song:
    chords = [
        ["E2", "B2", "E3", "G3", "B3", "E4"],
        ["C3", "E3", "G3", "B3", "E4", "G4"],
        ["G2", "B2", "D3", "G3", "B3", "G4"],
        ["D3", "A3", "D4", "F#4", "A4", "D5"],
    ]
    notes = []
    for bar, pitches in enumerate(chords):
        for step, index in enumerate([0, 2, 3, 4, 5, 4, 3, 2]):
            notes.append(
                Note(
                    pitch=pitches[index],
                    start=bar * 4 + step * 0.5,
                    duration=2.4,
                    velocity=0.8 if step == 0 else 0.58 + 0.025 * index,
                )
            )
    for index, pitch in enumerate(chords[0]):
        notes.append(
            Note(pitch=pitch, start=16 + index * 0.035, duration=2.7 - index * 0.035, velocity=0.7)
        )
    # A repeated fret damps the previous occurrence of that pitch. Preserve
    # ringing across other notes, while keeping note-offs unambiguous in MIDI.
    for index, note in enumerate(notes):
        next_start = next(
            (
                other.start
                for other in notes[index + 1 :]
                if midi_pitch(other.pitch) == midi_pitch(note.pitch)
            ),
            19,
        )
        notes[index] = Note(
            **{**note.model_dump(), "duration": min(note.duration, next_start - note.start - 0.01)}
        )
    return Song(
        title="Wood and Wire" if instrument == "guitar" else "Original Pluck Comparison",
        bpm=88,
        beats=19,
        seed=101,
        tracks=[
            Track(
                name="Fingerpicked phrase",
                instrument=instrument,
                gain=0.72,
                notes=notes,
                tone=Tone(brightness=0.55, decay_seconds=3.5, pluck_position=0.18)
                if instrument == "guitar"
                else None,
            ),
        ],
    )


def marimba_phrase() -> Song:
    melody = [
        "C5",
        "E5",
        "G5",
        "E5",
        "A5",
        "G5",
        "E5",
        "D5",
        "F5",
        "A5",
        "C6",
        "A5",
        "G5",
        "E5",
        "D5",
        "C5",
    ]
    notes = [
        Note(pitch=pitch, start=index * 0.75, duration=0.7, velocity=0.8 if index % 3 == 0 else 0.6)
        for index, pitch in enumerate(melody)
    ]
    notes.extend(
        Note(pitch=pitch, start=12 + index * 0.06, duration=3 - index * 0.06, velocity=0.65)
        for index, pitch in enumerate(["C5", "E5", "G5"])
    )
    bass = [
        Note(pitch=pitch, start=index * 3, duration=2.8, velocity=0.72)
        for index, pitch in enumerate(["C3", "A3", "F3", "G3", "C3"])
    ]
    return Song(
        title="Wooden Steps",
        bpm=112,
        beats=16,
        seed=102,
        tracks=[
            Track(
                name="Mallet melody",
                instrument="marimba",
                gain=0.8,
                pan=0.25,
                tone=Tone(brightness=0.65, decay_seconds=1.6),
                notes=notes,
            ),
            Track(
                name="Low bars",
                instrument="marimba",
                gain=0.55,
                pan=-0.25,
                tone=Tone(brightness=0.25, decay_seconds=2),
                notes=bass,
            ),
        ],
    )


def bell_phrase() -> Song:
    notes = [
        Note(pitch=pitch, start=index * 2, duration=6, velocity=0.6 + 0.04 * (index % 3))
        for index, pitch in enumerate(["C5", "G5", "E5", "D5", "G4", "C5"])
    ]
    return Song(
        title="Cast in Code",
        bpm=90,
        beats=18,
        seed=103,
        tracks=[
            Track(
                name="Metal resonances",
                instrument="bell",
                gain=0.85,
                tone=Tone(brightness=0.65, decay_seconds=5.5),
                notes=notes,
            ),
        ],
    )


def main() -> None:
    output = Path("output/physical-instruments")
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    examples = [
        (
            "00-original-pluck",
            guitar_phrase("pluck"),
            "Before: original synth",
            "The same fingerpicked score, rendered with the original harmonic pluck.",
        ),
        (
            "01-modeled-guitar",
            guitar_phrase(),
            "After: string model",
            "A generated pluck circulates through a tuned, damped string loop.",
        ),
        (
            "02-modeled-marimba",
            marimba_phrase(),
            "Struck-bar model",
            "Wooden-bar resonances lose their high overtones faster than the fundamental.",
        ),
        (
            "03-modeled-bell",
            bell_phrase(),
            "Metallic modal synthesis",
            "Inharmonic resonances ring and decay independently after each strike.",
        ),
    ]
    for slug, song, style, description in examples:
        song.save(output / f"{slug}.json")
        export_midi(song, output / f"{slug}.mid")
        report = render(song, output / f"{slug}.wav")
        (output / f"{slug}.report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        if report["wav"]["silent"] or report["wav"]["full_scale_samples"]:
            raise RuntimeError(f"{slug}: invalid audio output")
        entry = {
            "slug": slug,
            "title": song.title,
            "style": style,
            "description": description,
            "bpm": song.bpm,
            "duration_seconds": report["wav"]["duration_seconds"],
            "peak_dbfs": report["wav"]["peak_dbfs"],
            "rms_dbfs": report["wav"]["rms_dbfs"],
            "warnings": report["warnings"],
        }
        entries.append(entry)
        print(json.dumps(entry), flush=True)
    (output / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    write_gallery(
        output,
        entries,
        heading="Instruments, generated from equations.",
        introduction="Compare the original pluck with the new string model, then hear "
        "a modeled wooden bar and a metallic chime. All sound is generated from code. "
        "These are simplified models, not calibrated replicas of particular instruments.",
    )
    print(f"Listen: {(output / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
