"""Original before/after. Run: uv run --extra loudness python examples/groove_comparison.py.

Both scores share harmony, instruments, track gains, tempo, seed and duration.
Only the written rhythm, accents and phrase development change. Final files are
matched to -20 LUFS to reduce loudness bias, with no limiting or compression.
"""

import json
import wave
from pathlib import Path

from audio_as_code import Pattern, Reverb, Song, Track, export_midi, render


def comparison_song(*, developed: bool) -> Song:
    melody = []
    harmony = []
    bass = []
    # Two bars each: Dm9, G13, Cmaj9, A7. All notes are original.
    changes = [
        (["F3", "A3", "C4", "E4"], "D2", "A2", ["D4", "F4", "A4", "C5", "E5", "A4"]),
        (["F3", "A3", "B3", "E4"], "G2", "D3", ["D4", "G4", "B4", "D5", "E5", "B4"]),
        (["E3", "G3", "B3", "D4"], "C2", "G2", ["E4", "G4", "B4", "D5", "E5", "G4"]),
        (["E3", "G3", "A3", "C#4"], "A2", "E3", ["E4", "G4", "A4", "C#5", "E5", "A4"]),
    ]
    for section, (chord, root, fifth, pitches) in enumerate(changes):
        a, b, c, d, e, f = pitches
        motif = Pattern.sequence([a, None, b, c, None, d, e, f], step=0.5, gate=0.78, velocity=0.64)
        if developed:
            answer = motif.reverse().scale_velocity(0.88)
            if section == 3:
                # A deliberate closing gesture, rather than another mechanically reversed bar.
                answer = Pattern.sequence(
                    ["E5", "C#5", "A4", "G4", "E4", None, "D4", None],
                    step=0.5,
                    gate=0.9,
                    velocity=0.58,
                )
            phrase = motif.repeat(2, variations={1: answer}).accent([1, 0.72, 0.88, 0.78])
            phrase = phrase.swing(0.61)
        else:
            phrase = motif.repeat(2)
        melody.extend(phrase.at(section * 8))
        # Identical accompaniment makes the musical comparison easier to hear.
        harmony.extend(
            Pattern.sequence([chord, None, chord, None], step=2, gate=0.85, velocity=0.48).at(
                section * 8
            )
        )
        bass.extend(
            Pattern.sequence([root, None, fifth, root], gate=0.65, velocity=0.6)
            .repeat(2)
            .at(section * 8)
        )

    kick = Pattern.sequence([36, None, 36, None], gate=0.2, velocity=0.72).repeat(8)
    snare = Pattern.sequence([None, 38, None, 38], gate=0.16, velocity=0.52)
    hats = Pattern.sequence([42] * 8, step=0.5, gate=0.18, velocity=0.44)
    if developed:
        fill = Pattern.sequence(
            [None, 38, None, 38, None, 38, 38, 38], step=0.5, gate=0.2, velocity=0.45
        ).accent([0.65, 1])
        snare = snare.repeat(8, variations={3: fill, 7: fill}).swing(0.61)
        sparse = Pattern.euclidean(5, 8, pitch=42, rotation=1, gate=0.18, velocity=0.44)
        hats = hats.repeat(8, variations={1: sparse, 3: sparse, 5: sparse, 7: sparse})
        hats = hats.accent([1, 0.55, 0.8, 0.6]).swing(0.61)
    else:
        snare = snare.repeat(8)
        hats = hats.repeat(8)

    # Shared two-beat cadence also gives both versions the same natural tail.
    melody.extend(Pattern.sequence(["D4", None], gate=0.9, velocity=0.58).at(32))
    harmony.extend(
        Pattern.sequence([["F3", "A3", "C4", "E4"]], step=2, gate=0.85, velocity=0.48).at(32)
    )
    bass.extend(Pattern.sequence(["D2", None], gate=0.8, velocity=0.6).at(32))

    return Song(
        title="Late afternoon: " + ("developed groove" if developed else "straight sketch"),
        bpm=106,
        beats=34,
        seed=19,
        tracks=(
            Track(
                name="Melody",
                instrument="marimba",
                gain=0.8,
                pan=0.18,
                notes=tuple(melody),
                release_seconds=0.12,
                effects=(Reverb(mix=0.1, decay_seconds=0.6),),
            ),
            Track(
                name="Harmony",
                instrument="electric_piano",
                gain=0.42,
                pan=-0.22,
                notes=tuple(harmony),
                release_seconds=0.18,
            ),
            Track(name="Bass", instrument="bass", gain=0.5, notes=tuple(bass)),
            Track(name="Kick", instrument="kick", gain=0.65, notes=kick.notes),
            Track(name="Snare", instrument="snare", gain=0.4, pan=-0.08, notes=snare.notes),
            Track(name="Hats", instrument="hat", gain=0.5, pan=0.3, notes=hats.notes),
        ),
    )


def main() -> None:
    output = Path("output/groove-comparison")
    reports = {}
    for label, developed in [("before", False), ("after", True)]:
        song = comparison_song(developed=developed)
        song.save(output / f"{label}.json")
        export_midi(song, output / f"{label}.mid")
        report = render(song, output / f"{label}.wav", target_lufs=-20)
        if not report["loudness"]["target_reached"]:
            raise RuntimeError("Loudness target was not reached; comparison needs review")
        reports[label] = report
    # A single listening file: before, one second of silence, then after.
    with wave.open(str(output / "before.wav"), "rb") as before:
        params = before.getparams()
        first = before.readframes(before.getnframes())
    with wave.open(str(output / "after.wav"), "rb") as after:
        if after.getparams() != params:
            raise RuntimeError("Comparison audio formats or durations differ")
        second = after.readframes(after.getnframes())
    with wave.open(str(output / "before-then-after.wav"), "wb") as combined:
        combined.setparams(params)
        combined.writeframes(
            first + bytes(params.framerate * params.nchannels * params.sampwidth) + second
        )
    (output / "report.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({label: report["loudness"] for label, report in reports.items()}, indent=2))


if __name__ == "__main__":
    main()
