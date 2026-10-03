"""Song form: intro, verse, chorus, bridge, final chorus, and ending.

Run from the root of a source checkout:

    python docs/site/examples/03_song_form.py [output-directory]

The score has no section objects. Sections are a plain Python table of
start beats; each part is written by functions that take a section and
return notes on the absolute timeline. Dynamics come from velocity and
from which tracks play in each section. Writes score.json, song.wav,
song.mid, stems/, report.json, and sections.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from audio_as_code import Note, Pattern, Song, Tone, Track, export_midi, render

out = Path(sys.argv[1] if len(sys.argv) > 1 else "output/docs-examples/03-song-form")

BPM = 92
BAR = 4
# (name, bars, chords): one chord symbol per bar, spelled as root + voicing.
CHORDS = {
    "Dm": ("D2", ["D3", "F3", "A3", "C4"]),
    "Bb": ("Bb1", ["D3", "F3", "Bb3", "D4"]),
    "F": ("F2", ["C3", "F3", "A3", "C4"]),
    "C": ("C2", ["C3", "E3", "G3", "C4"]),
    "Gm": ("G2", ["D3", "G3", "Bb3", "D4"]),
    "A": ("A1", ["C#3", "E3", "A3", "C#4"]),
}
FORM = [
    ("intro", ["Dm", "Bb", "Dm", "Bb"]),
    ("verse", ["Dm", "Bb", "F", "C", "Dm", "Bb", "Gm", "A"]),
    ("chorus", ["F", "C", "Dm", "Bb", "F", "C", "Gm", "A"]),
    ("bridge", ["Gm", "Dm", "Gm", "A"]),
    ("chorus 2", ["F", "C", "Dm", "Bb", "F", "C", "Gm", "A"]),
    ("ending", ["Dm", "Dm"]),
]

# Turn the form into absolute beat positions.
sections = []
beat = 0
for name, bars in FORM:
    sections.append({"name": name, "start": beat, "bars": bars})
    beat += len(bars) * BAR
END = beat  # 136 beats

verse_motif = Pattern.sequence(
    ["A4", None, "A4", "G4", "F4", None, "E4", "D4"], step=0.5, gate=0.8, velocity=0.62
)
chorus_motif = Pattern.sequence(
    ["C5", None, "A4", "C5", "D5", None, "C5", "A4"], step=0.5, gate=0.8, velocity=0.78
)


def harmony(section: dict, velocity: float, length: float = 3.9) -> list[Note]:
    notes = []
    for bar, symbol in enumerate(section["bars"]):
        at = section["start"] + bar * BAR
        notes += [
            Note(pitch=p, start=at, duration=length, velocity=velocity) for p in CHORDS[symbol][1]
        ]
    return notes


def bassline(section: dict, velocity: float, busy: bool) -> list[Note]:
    notes = []
    for bar, symbol in enumerate(section["bars"]):
        root = CHORDS[symbol][0]
        steps = (
            [root, None, root, None, root, root, None, None] if busy else [root, None, None, None]
        )
        step = 0.5 if busy else 1
        notes += Pattern.sequence(steps, step=step, gate=0.85, velocity=velocity).at(
            section["start"] + bar * BAR
        )
    return notes


def melody(section: dict, motif: Pattern) -> list[Note]:
    """Play the motif in odd bars; follow the chord root a sixth up in the even bars."""
    notes = []
    for bar, symbol in enumerate(section["bars"]):
        at = section["start"] + bar * BAR
        if bar % 2 == 0:
            notes += motif.at(at)
        else:
            answer = Pattern.sequence([CHORDS[symbol][1][-1], None], step=2, gate=0.9)
            notes += answer.transpose(12).at(at)
    return notes


def drums(section: dict, fill: bool) -> list[Note]:
    """drum_machine selects the voice by pitch: 36 kick, 38 snare, 42 hat, 45 tom, 49 cymbal."""
    groove = Pattern.sequence(
        [[36, 42], 42, [38, 42], 42, [36, 42], [36, 42], [38, 42], 42],
        step=0.5,
        gate=0.3,
        velocity=0.7,
    )
    bars = len(section["bars"])
    notes = list(groove.repeat(bars - 1 if fill else bars).at(section["start"]))
    if fill:
        tom_fill = Pattern.sequence(
            [45, 45, 38, 45, 38, 38, 38, 38], step=0.5, gate=0.3, velocity=0.8
        )
        notes += tom_fill.at(section["start"] + (bars - 1) * BAR)
    return notes


by_name = {s["name"]: s for s in sections}
intro, verse, chorus, bridge, chorus2, ending = (by_name[n] for n, _ in FORM)

piano = harmony(intro, 0.45) + harmony(verse, 0.5) + harmony(chorus, 0.62)
piano += harmony(bridge, 0.4) + harmony(chorus2, 0.68)
piano += [Note(pitch=p, start=ending["start"], duration=7.5, velocity=0.5) for p in CHORDS["Dm"][1]]
cello = harmony(bridge, 0.6, length=3.8)[::4]  # just the lowest voice of each bridge chord
bass = bassline(verse, 0.7, busy=False) + bassline(chorus, 0.8, busy=True)
bass += bassline(chorus2, 0.85, busy=True)
bass.append(Note(pitch="D2", start=ending["start"], duration=6, velocity=0.7))
lead = melody(verse, verse_motif) + melody(chorus, chorus_motif) + melody(chorus2, chorus_motif)
lead.append(Note(pitch="D5", start=ending["start"], duration=6, velocity=0.6))
kit = drums(verse, fill=True) + drums(chorus, fill=True) + drums(chorus2, fill=False)
kit.append(Note(pitch=49, start=ending["start"], duration=6, velocity=0.6))

song = Song(
    title="Song form",
    bpm=BPM,
    beats=END,
    seed=3,
    tracks=[
        Track(
            name="Piano",
            instrument="piano",
            gain=0.38,
            pan=-0.2,
            tone=Tone(brightness=0.45),
            notes=tuple(piano),
        ),
        Track(name="Bridge cello", instrument="cello", gain=0.5, pan=-0.35, notes=tuple(cello)),
        Track(name="Bass", instrument="bass_guitar", gain=0.62, notes=tuple(bass)),
        Track(name="Flute lead", instrument="flute", gain=0.42, pan=0.25, notes=tuple(lead)),
        Track(name="Kit", instrument="drum_machine", gain=0.45, notes=tuple(kit)),
    ],
)

song.save(out / "score.json")
report = render(song, out / "song.wav", stems_dir=out / "stems")
export_midi(song, out / "song.mid")
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
seconds_per_beat = 60 / BPM
table = [
    {
        "name": s["name"],
        "start_beat": s["start"],
        "end_beat": s["start"] + len(s["bars"]) * BAR,
        "start_seconds": round(s["start"] * seconds_per_beat, 2),
    }
    for s in sections
]
(out / "sections.json").write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
for row in table:
    beats = f"{row['start_beat']:>3}-{row['end_beat']:<3}"
    print(f"{row['name']:>9}  beats {beats}  at {row['start_seconds']:6.2f} s")
print(f"total {song.seconds:.1f} s, peak {report['wav']['peak']:.3f}")
print("warnings:", report["warnings"] or "none")
