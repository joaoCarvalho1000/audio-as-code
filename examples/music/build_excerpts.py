"""Optional source-data rebuild. Downloads notation MIDI, never instrument audio.

Normal demo generation reads excerpts.json offline and does not run this script.
"""

from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import mido

BASE = "https://www.mutopiaproject.org/"
SOURCES = {
    "greensleeves": {
        "title": "Greensleeves",
        "composer": "Traditional",
        "credit": "Aaron Fontaine",
        "source_id": 109,
        "path": "ftp/Traditional/Greensleaves/Greensleaves.mid",
        "beats": 24,
        "bpm": 100,
    },
    "ode_to_joy": {
        "title": "Ode to Joy",
        "composer": "Ludwig van Beethoven",
        "credit": "Peter Chubb",
        "source_id": 528,
        "path": "ftp/BeethovenLv/ode/ode.mid",
        "beats": 32,
        "bpm": 104,
    },
    "fur_elise": {
        "title": "Für Elise",
        "composer": "Ludwig van Beethoven",
        "credit": "Stelios Samelis",
        "source_id": 931,
        "path": "ftp/BeethovenLv/WoO59/fur_Elise_WoO59/fur_Elise_WoO59.mid",
        "beats": 12,
        "bpm": 66,
    },
    "turkish_march": {
        "title": "Turkish March",
        "composer": "Wolfgang Amadeus Mozart",
        "credit": "Rune Zedeler and Chris Sawer",
        "source_id": 108,
        "path": "ftp/MozartWA/KV331/KV331_3_RondoAllaTurca/KV331_3_RondoAllaTurca.mid",
        "beats": 32,
        "bpm": 112,
    },
    "cello_prelude": {
        "title": "Cello Suite No. 1 · Prelude",
        "composer": "Johann Sebastian Bach",
        "credit": "Andreas Scherer",
        "source_id": 517,
        "path": "ftp/BachJS/BWV1007/bwv1007/bwv1007-mids.zip",
        "member": "bwv1007.mid",
        "beats": 32,
        "bpm": 84,
    },
}


def track_notes(track: mido.MidiTrack, resolution: int, end: float) -> list[list[float]]:
    """Retain pitch/onset/duration; ignore MIDI programs, effects, and audio."""
    active: dict[tuple[int, int], tuple[int, int]] = {}
    result = []
    tick = 0
    for message in track:
        tick += message.time
        if message.type not in {"note_on", "note_off"}:
            continue
        key = (message.channel, message.note)
        if message.type == "note_on" and message.velocity:
            if key in active:
                raise ValueError(f"Ambiguous source note overlap: {key}")
            active[key] = (tick, message.velocity)
        elif key in active:
            start, _velocity = active.pop(key)
            onset = start / resolution
            if onset < end:
                duration = min(tick / resolution, end) - onset
                if duration > 0:
                    result.append([message.note, round(onset, 6), round(duration, 6)])
    return sorted(result, key=lambda n: (n[1], n[0]))


def upper_voice(notes: list[list[float]]) -> list[list[float]]:
    """Keep notes that start as the highest sounding voice in this short excerpt."""
    return [
        note
        for note in notes
        if not any(
            other[0] > note[0] and other[1] <= note[1] < other[1] + other[2] - 1e-5
            for other in notes
        )
    ]


def ode_voices() -> dict[str, list[list[float]]]:
    # Separate the first eight bars of Peter Chubb's LilyPond voices. MIDI merges
    # coincident unisons, so direct voice transcription preserves the four parts.
    pitches = {
        "melody": [
            71,
            71,
            72,
            74,
            74,
            72,
            71,
            69,
            67,
            67,
            69,
            71,
            71,
            69,
            69,
            71,
            71,
            72,
            74,
            74,
            72,
            71,
            69,
            67,
            67,
            69,
            71,
            69,
            67,
            67,
        ],
        "alto": [
            67,
            67,
            69,
            67,
            67,
            69,
            67,
            66,
            62,
            62,
            66,
            67,
            67,
            66,
            66,
            67,
            67,
            69,
            67,
            67,
            69,
            67,
            66,
            62,
            62,
            66,
            67,
            67,
            66,
            62,
        ],
        "tenor": [
            62,
            62,
            60,
            59,
            64,
            62,
            62,
            62,
            59,
            59,
            62,
            62,
            62,
            62,
            62,
            62,
            62,
            60,
            59,
            64,
            62,
            62,
            62,
            59,
            59,
            62,
            62,
            62,
            62,
            59,
        ],
        "bass": [
            55,
            55,
            55,
            55,
            52,
            54,
            55,
            50,
            59,
            59,
            57,
            55,
            50,
            50,
            50,
            55,
            55,
            55,
            55,
            52,
            54,
            55,
            50,
            59,
            59,
            57,
            55,
            50,
            50,
            43,
        ],
    }
    result = {}
    for part, values in pitches.items():
        durations = [1.0] * len(values)
        for offset in (0, 15):
            if part != "melody":
                durations[offset + 4 : offset + 6] = [1.5, 0.5]
            durations[offset + 12 : offset + 15] = (
                [1.5, 0.5, 2.0] if offset == 0 or part == "melody" else [1.0, 1.0, 2.0]
            )
        at = 0.0
        notes = []
        for pitch, duration in zip(values, durations, strict=True):
            notes.append([pitch, at, duration])
            at += duration
        assert at == 32
        result[part] = notes
    return result


def main() -> None:
    pieces = {}
    for key, spec in SOURCES.items():
        data = urllib.request.urlopen(BASE + spec["path"], timeout=30).read()
        digest = hashlib.sha256(data).hexdigest()
        if "member" in spec:
            data = zipfile.ZipFile(io.BytesIO(data)).read(spec["member"])
        midi = mido.MidiFile(file=io.BytesIO(data))
        tracks = [track_notes(track, midi.ticks_per_beat, spec["beats"]) for track in midi.tracks]
        tracks = [notes for notes in tracks if notes]
        if key == "ode_to_joy":
            parts = ode_voices()
        else:
            melody = upper_voice(tracks[0])
            parts = {"melody": melody}
            remainder = [note for note in tracks[0] if note not in melody]
            if remainder:
                parts["inner"] = remainder
            if len(tracks) > 1:
                parts["accompaniment"] = tracks[1]
        pieces[key] = {
            **spec,
            "license": "Public Domain",
            "download_url": BASE + spec["path"],
            "source_url": BASE + f"cgibin/piece-info.cgi?id={spec['source_id']}",
            "source_sha256": digest,
            "parts": parts,
        }
    destination = Path(__file__).with_name("excerpts.json")
    destination.write_text(
        json.dumps(pieces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(pieces)} public-domain score excerpts to {destination}")


if __name__ == "__main__":
    main()
