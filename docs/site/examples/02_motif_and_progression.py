"""Motifs, a chord progression, and arrangement with Pattern.

Run from the root of a source checkout:

    python docs/site/examples/02_motif_and_progression.py [output-directory]

One two-bar motif is transposed to follow a I-vi-IV-V progression, answered
by a varied phrase, and accompanied by voiced chords, a walking bass, and
an arpeggio. Output goes to output/docs-examples/02-motif-and-progression/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from audio_as_code import Note, Pattern, Song, Track, export_midi, render

out = Path(sys.argv[1] if len(sys.argv) > 1 else "output/docs-examples/02-motif-and-progression")

BAR = 4  # beats per bar in this 4/4 piece

# The progression: C major, A minor, F major, G major. One chord per bar.
roots = ["C3", "A2", "F2", "G2"]
fifths = ["G2", "E2", "C3", "D3"]
approach = ["B2", "G2", "F#2", "B2"]  # a step away from the next bar's root
voicings = [
    ["E3", "G3", "C4"],
    ["E3", "A3", "C4"],
    ["F3", "A3", "C4"],
    ["D3", "G3", "B3"],
]  # close voicings that move by step instead of jumping in parallel

# A two-bar motif (8 beats, including its final rest).
motif = Pattern.sequence(
    ["G4", None, "E4", "G4", "A4", "G4", "E4", None]  # bar 1
    + ["D4", "E4", "G4", None, "E4", None, None, None],  # bar 2
    step=0.5,
    gate=0.7,
    velocity=0.72,
)
# A contrasting two-bar answer that settles on the tonic, C.
answer = Pattern.sequence(
    ["C5", None, "A4", "G4", "E4", None, "D4", "C4"]
    + ["D4", None, "E4", "D4", "C4", None, None, None],
    step=0.5,
    gate=0.7,
    velocity=0.68,
)
# transpose() counts semitones: -3 repeats the motif a minor third lower over A minor.
phrase_a = motif.then(motif.transpose(-3))  # bars 1-4
phrase_b = motif.transpose(2).then(answer)  # bars 5-8: a step higher, then the answer
lead = phrase_a.then(phrase_b)  # 16 beats + 16 beats = 32 beats


def chord(pitches: list[str], start: float, duration: float, velocity: float) -> list[Note]:
    """A block chord is several notes with the same start; there is no chord object."""
    return [Note(pitch=p, start=start, duration=duration, velocity=velocity) for p in pitches]


pads: list[Note] = []
bass: list[Note] = []
arp: list[Note] = []
for bar in range(8):
    at = bar * BAR
    i = bar % 4
    pads += chord(voicings[i], at, 3.9, 0.5)
    # Bass: root, rest, fifth, then an approach note leading into the next bar.
    bass += Pattern.sequence([roots[i], None, fifths[i], approach[i]], gate=0.8).at(at)
    # Arpeggiate the chord tones an octave up in eighth notes (8 steps = 4 beats).
    broken = Pattern.sequence(voicings[i] * 2 + [voicings[i][1], None], step=0.5, gate=0.5)
    arp += broken.transpose(12).at(at)

# Accents: Pattern sets one velocity for all steps; rebuild notes to vary it.
accented_arp = [
    Note(**{**n.model_dump(), "velocity": 0.55 if n.start % 2 == 0 else 0.35}) for n in arp
]
kick = Pattern.sequence([36, None, None, 36, None, 36, None, None], step=0.5, gate=0.3)  # 1 bar
snare = Pattern.sequence([None, 38], step=2, gate=0.15, velocity=0.6)  # backbeat on beat 3

song = Song(
    title="Motif and progression",
    bpm=108,
    beats=33,  # 32 beats of music plus one beat for the last notes to fade
    seed=2,
    tracks=[
        Track(name="Lead", instrument="marimba", gain=0.6, pan=0.15, notes=lead.notes),
        Track(name="Chords", instrument="electric_piano", gain=0.32, pan=-0.3, notes=tuple(pads)),
        Track(name="Arpeggio", instrument="harp", gain=0.3, pan=0.45, notes=tuple(accented_arp)),
        Track(name="Bass", instrument="bass_guitar", gain=0.7, notes=tuple(bass)),
        Track(name="Kick", instrument="kick", gain=0.75, notes=kick.repeat(8).notes),
        Track(name="Snare", instrument="snare", gain=0.45, notes=snare.repeat(8).notes),
    ],
)

song.save(out / "score.json")
report = render(song, out / "song.wav")
export_midi(song, out / "song.mid")
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(f"{song.title}: {sum(len(t.notes) for t in song.tracks)} notes, {song.seconds:.1f} s")
print(f"lead pattern: {len(lead.notes)} notes over {lead.beats} beats")
print(f"peak {report['wav']['peak']:.3f}, gain applied {report['gain_applied']:.3f}")
print("warnings:", report["warnings"] or "none")
