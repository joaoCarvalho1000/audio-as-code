"""Import complete public-domain notation, explicitly unfolding printed repeats.

This optional rebuild downloads MIDI/LilyPond notation, never instrument audio.
Normal playback reads classics-full.json offline. Edition-specific repeat maps
are checked against source lengths and saved alongside the portable notes.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.request
import zipfile
from collections import Counter
from fractions import Fraction
from pathlib import Path

import mido

BASE = "https://www.mutopiaproject.org/"
SPECS = {
    "fur_elise": {
        "title": "Für Elise",
        "composer": "Ludwig van Beethoven",
        "credit": "Stelios Samelis",
        "id": 931,
        "base": "ftp/BeethovenLv/WoO59/fur_Elise_WoO59/fur_Elise_WoO59",
        "bpm": 72,
        "source_beats": 156.5,
        "scope": "Complete Für Elise, WoO 59, with printed repeats",
        "parts": ["right", "left"],
    },
    "cello_prelude": {
        "title": "Cello Suite No. 1 · Prelude",
        "composer": "Johann Sebastian Bach",
        "credit": "Andreas Scherer",
        "id": 517,
        "base": "ftp/BachJS/BWV1007/bwv1007/bwv1007",
        "bpm": 80,
        "source_beats": 168,
        "scope": "Complete Prelude from Cello Suite No. 1, BWV 1007 (not the six-movement suite)",
        "parts": ["cello"],
        "midi_suffix": "-mids.zip",
        "ly_suffix": "-lys.zip",
        "member": "bwv1007.mid",
    },
    "turkish_march": {
        "title": "Turkish March",
        "composer": "Wolfgang Amadeus Mozart",
        "credit": "Rune Zedeler and Chris Sawer",
        "id": 108,
        "base": "ftp/MozartWA/KV331/KV331_3_RondoAllaTurca/KV331_3_RondoAllaTurca",
        "bpm": 112,
        "source_beats": 255,
        "ly_suffix": "-lys.zip",
        "scope": "Complete Rondo alla Turca, K. 331 third movement, with printed repeats",
        "parts": ["right", "left"],
    },
    "greensleeves": {
        "title": "Greensleeves",
        "composer": "Traditional",
        "credit": "Aaron Fontaine",
        "id": 109,
        "base": "ftp/Traditional/Greensleaves/Greensleaves",
        "bpm": 100,
        "source_beats": 97,
        "scope": (
            "Complete Aaron Fontaine two-voice lute/guitar arrangement, all 32 bars and pickup"
        ),
        "parts": ["combined"],
    },
    "ode_to_joy": {
        "title": "Ode to Joy",
        "composer": "Ludwig van Beethoven",
        "credit": "Peter Chubb",
        "id": 528,
        "base": "ftp/BeethovenLv/ode/ode",
        "bpm": 100,
        "source_beats": 64,
        "scope": (
            "Complete Peter Chubb 16-bar SATB hymn arrangement (not Beethoven's Ninth Symphony)"
        ),
        "parts": ["upper", "lower"],
    },
}


# Folded MIDI places volta bodies once and both alternative endings consecutively.
# Each tuple is (label, source start beat, source end beat). Repetition here follows
# the printed source, never an arbitrary loop used to lengthen an excerpt.
FUR_FORM = [
    ("A · first statement", 0, 12),
    ("A · repeat", 0, 11),
    ("A · second ending", 12, 13.5),
    ("B and A · first pass", 13.5, 34.5),
    ("B and A · repeat", 13.5, 33),
    ("Second ending", 34.5, 36),
    ("Episodes and final returns", 36, 156.5),
]
TURKISH_FORM = []
for label, start, end in [
    ("A-minor opening", 0, 16),
    ("Answer and return", 16, 48),
    ("A-major march", 48, 64),
    ("F-sharp-minor run", 64, 80),
    ("Contrasting episode", 80, 112),
    ("March return", 112, 128),
    ("A-minor return", 128, 144),
    ("Answer reprise", 144, 176),
]:
    TURKISH_FORM += [(label, start, end), (label + " · repeat", start, end)]
TURKISH_FORM += [
    ("Octave march · first pass", 176, 192),
    ("Octave march · repeat", 176, 191),
    ("Second ending", 192, 194),
    ("Coda", 194, 255),
]


def midi_notes(track: mido.MidiTrack, resolution: int) -> tuple[list, float]:
    active, rows, tick = {}, [], 0
    for message in track:
        tick += message.time
        if message.type not in {"note_on", "note_off"}:
            continue
        identity = (message.channel, message.note)
        if message.type == "note_on" and message.velocity:
            if identity in active:
                raise ValueError(f"Overlapping source MIDI key: {identity}")
            active[identity] = (tick, message.velocity)
        else:
            if identity not in active:
                raise ValueError(f"Unmatched source note-off: {identity}")
            start, velocity = active.pop(identity)
            if tick <= start:
                raise ValueError("Zero-length source note")
            rows.append(
                [message.note, start / resolution, (tick - start) / resolution, velocity / 127]
            )
    if active:
        raise ValueError("Source MIDI ends with hanging notes")
    return sorted(rows, key=lambda n: (n[1], n[0])), tick / resolution


def expand(parts: dict, form: list, *, turkish: bool = False) -> tuple[dict, list, list]:
    output = {name: [] for name in parts}
    sections, mapping, at = [], [], 0.0
    for label, start, end in form:
        sections.append({"name": label, "start_beat": at, "end_beat": at + end - start})
        mapping.append(
            {
                "name": label,
                "source_start_beat": start,
                "source_end_beat": end,
                "performance_start_beat": at,
                "performance_end_beat": at + end - start,
            }
        )
        for name, rows in parts.items():
            for pitch, onset, duration, velocity in rows:
                if not start <= onset < end:
                    continue
                if onset + duration > end + 1e-9:
                    raise ValueError(f"Repeat boundary crosses held source note: {name}, {onset}")
                # Mozart's manual alternative engraving includes a hidden right-hand
                # grace note and left-hand grace arpeggio BEFORE the second ending.
                # Move those pickups to the second pass; do not play them at ending 1.
                if turkish and start == 176 and end == 192:
                    if onset >= 191 + 351 / 384:
                        continue
                    if onset == 191:
                        duration = 1.0
                if turkish and start == 176 and end == 191:
                    if onset + duration == 191:
                        duration -= 33 / 384
                output[name].append([pitch, at + onset - start, duration, velocity])
            if turkish and start == 192:
                for pitch, onset, duration, velocity in rows:
                    if 191 + 351 / 384 <= onset < 192:
                        output[name].append([pitch, at + onset - 192, duration, velocity])
        at += end - start
    for rows in output.values():
        rows.sort(key=lambda n: (n[1], n[0]))
    return output, sections, mapping


def ode_parts(text: str, midi_parts: dict) -> dict:
    """Parse only this edition's four explicit absolute-pitch LilyPond voices.

    No general LilyPond evaluator, scheme execution, inferred harmonization or
    voice separation: each voice is written explicitly in the verified source.
    """
    output = {}
    for source_name, name, shift in [
        ("sop", "soprano", 12),
        ("alto", "alto", 12),
        ("tenor", "tenor", 0),
        ("bass", "bass", 0),
    ]:
        match = re.search(r"(?m)^" + source_name + r"\s*=.*?\{(.*?)\}", text, re.S)
        if match is None:
            raise ValueError(f"Missing source voice: {source_name}")
        body = re.sub(r'\\[A-Za-z]+|"[^"]*"', "", match.group(1))
        tokens = re.findall(r"\b([a-g](?:is|es)?)([',]*)([0-9]*)(\.*)", body)
        at, duration, rows = Fraction(0), Fraction(1), []
        for pitch, octave, denominator, dots in tokens:
            if denominator:
                duration = Fraction(4, int(denominator)) * sum(
                    Fraction(1, 2**i) for i in range(len(dots) + 1)
                )
            semitone = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}[pitch[0]]
            accidental = 1 if pitch.endswith("is") else -1 if pitch.endswith("es") else 0
            number = 48 + semitone + accidental + 12 * (octave.count("'") - octave.count(","))
            rows.append([number + shift, float(at), float(duration), 90 / 127])
            at += duration
        if at != 64:
            raise ValueError(f"SATB voice must contain all sixteen bars: {name}, {at}")
        output[name] = rows
    # LilyPond MIDI merges simultaneous unisons, sometimes extending their gate.
    # Verify the source's sounding pitches at every eighth-note boundary instead
    # of incorrectly requiring the four notation parts to have the merged count.
    for half_beat in range(128):
        beat = half_beat / 2 + 0.001
        notation = {p for rows in output.values() for p, s, d, _v in rows if s <= beat < s + d}
        encoded = {p for rows in midi_parts.values() for p, s, d, _v in rows if s <= beat < s + d}
        if notation != encoded:
            raise ValueError(
                f"SATB notation/MIDI disagreement at beat {beat}: {notation ^ encoded}"
            )
    return output


def _download(url: str, destination: Path) -> bytes:
    if not destination.exists():
        destination.write_bytes(urllib.request.urlopen(url, timeout=30).read())
    return destination.read_bytes()


def main() -> None:
    cache = Path("output/classic-showcase/source-notation")
    cache.mkdir(parents=True, exist_ok=True)
    notation = Path(__file__).with_name("classics-sources")
    notation.mkdir(exist_ok=True)
    result = {}
    for key, spec in SPECS.items():
        midi_url = BASE + spec["base"] + spec.get("midi_suffix", ".mid")
        is_archive = "member" in spec
        raw = _download(midi_url, cache / (key + (".zip" if is_archive else ".mid")))
        data = zipfile.ZipFile(io.BytesIO(raw)).read(spec["member"]) if is_archive else raw
        (cache / (key + ".mid")).write_bytes(data)
        midi = mido.MidiFile(file=io.BytesIO(data))
        decoded = [midi_notes(track, midi.ticks_per_beat) for track in midi.tracks]
        raw_parts = [rows for rows, _end in decoded if rows]
        source_end = max(end for _rows, end in decoded)
        if source_end != spec["source_beats"] or len(raw_parts) != len(spec["parts"]):
            raise ValueError(f"Source edition changed: {key}, {source_end}")
        parts = dict(zip(spec["parts"], raw_parts, strict=True))
        ly_url = BASE + spec["base"] + spec.get("ly_suffix", ".ly")
        ly_archive = ly_url.endswith(".zip")
        ly_data = _download(ly_url, cache / (key + ("-notation.zip" if ly_archive else ".ly")))
        ly_files = {}
        if ly_archive:
            with zipfile.ZipFile(io.BytesIO(ly_data)) as archive:
                for name in archive.namelist():
                    if name.endswith((".ly", ".ily")):
                        ly_files[Path(name).name] = archive.read(name)
        else:
            ly_files[key + ".ly"] = ly_data
        for name, content in ly_files.items():
            (notation / (key + "-" + name)).write_bytes(content)
        form = (
            FUR_FORM
            if key == "fur_elise"
            else TURKISH_FORM
            if key == "turkish_march"
            else [("Complete source arrangement", 0, source_end)]
        )
        if key == "ode_to_joy":
            parts = ode_parts(ly_data.decode("utf-8-sig"), parts)
        elif key == "greensleeves":
            rows = parts["combined"]
            melody = [
                row
                for row in rows
                if not any(
                    other[0] > row[0] and other[1] <= row[1] < other[1] + other[2] - 1e-9
                    for other in rows
                )
            ]
            parts = {"melody": melody, "harmony": [row for row in rows if row not in melody]}
        performed, sections, mapping = expand(parts, form, turkish=key == "turkish_march")
        beats = sections[-1]["end_beat"]
        if key in {"cello_prelude", "greensleeves", "ode_to_joy"}:
            # Source-based listening landmarks, without adding or repeating notes.
            marks = (
                {
                    "cello_prelude": [
                        ("Opening arpeggios", 0, 88),
                        ("Development", 88, 124),
                        ("Pedal and final chord", 124, 168),
                    ],
                    "greensleeves": [
                        ("Opening strain and written return", 0, 49),
                        ("Second strain and written return", 49, 97),
                    ],
                    "ode_to_joy": [
                        ("First phrase", 0, 16),
                        ("Answer", 16, 32),
                        ("Contrasting phrase", 32, 48),
                        ("Final phrase", 48, 64),
                    ],
                }
            )[key]
            sections = [{"name": n, "start_beat": s, "end_beat": e} for n, s, e in marks]
        # Every raw note-on must occur at least once in the performance. Ode's
        # authoritative separate notation voices are checked against sounding MIDI above.
        if key != "ode_to_joy":
            raw_pitches = Counter(row[0] for rows in parts.values() for row in rows)
            played = Counter(row[0] for rows in performed.values() for row in rows)
            if any(played[pitch] < count for pitch, count in raw_pitches.items()):
                raise ValueError(f"Missing source note-on: {key}")
        result[key] = {
            "title": spec["title"],
            "composer": spec["composer"],
            "credit": spec["credit"],
            "scope": spec["scope"],
            "source_url": BASE + f"cgibin/piece-info.cgi?id={spec['id']}",
            "license": "Public Domain",
            "source_verified_date": "2026-10-02",
            "download_url": midi_url,
            "notation_url": ly_url,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "midi_member_sha256": hashlib.sha256(data).hexdigest(),
            "notation_sha256": hashlib.sha256(ly_data).hexdigest(),
            "notation_files": [key + "-" + name for name in ly_files],
            "source_midi_beats": source_end,
            "source_midi_seconds": midi.length,
            "source_midi_notes": sum(len(rows) for rows in raw_parts),
            "beats": beats,
            "bpm": spec["bpm"],
            "parts": performed,
            "sections": sections,
            "repeat_expansion": mapping,
            "performance_notes": sum(len(rows) for rows in performed.values()),
            "repeat_policy": "Printed volta repeats and alternatives explicitly expanded from "
            "verified LilyPond; source MIDI is folded. No arbitrary looping."
            if key in {"fur_elise", "turkish_march"}
            else "Complete source sequence; no extra repeats.",
            "import_notes": "Mozart manual-ending grace pickups move before the second ending; "
            "first-ending held notes are restored and the repeat's preceding gates shortened "
            "by the same 33/384-beat grace allocation."
            if key == "turkish_march"
            else (
                "Ode's four explicit LilyPond voices are retained, "
                "including unisons merged by MIDI."
            )
            if key == "ode_to_joy"
            else "All source MIDI note pitches, onsets, gates and velocities retained.",
        }
        print(
            f"{key}: {beats} beats, {result[key]['performance_notes']} notes, "
            f"{beats * 60 / spec['bpm']:.2f} seconds",
            flush=True,
        )
    destination = Path(__file__).with_name("classics-full.json")
    destination.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
