"""Offline, short arrangements of five public-domain works for all catalog voices."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from audio_as_code import Note, Song, Tone, Track
from audio_as_code.instruments import InstrumentInfo, get_instrument

# piece, octave transposition in semitones, source parts. These are arrangements,
# not claims that the originals were written for these instruments.
SOLOS = {
    "guitar": ("greensleeves", -12, ("melody",)),
    "electric_guitar": ("turkish_march", -12, ("melody",)),
    "bass_guitar": ("cello_prelude", -12, ("melody",)),
    "harp": ("greensleeves", 0, ("melody", "inner")),
    "ukulele": ("greensleeves", 0, ("melody",)),
    "banjo": ("turkish_march", -12, ("melody",)),
    "mandolin": ("turkish_march", -12, ("melody",)),
    "kalimba": ("greensleeves", 0, ("melody",)),
    "celesta": ("fur_elise", 12, ("melody",)),
    "recorder": ("greensleeves", 12, ("melody",)),
    "viola": ("cello_prelude", 12, ("melody",)),
    "cello": ("cello_prelude", 0, ("melody",)),
    "double_bass": ("cello_prelude", -12, ("melody",)),
    "piano": ("fur_elise", 0, ("melody", "accompaniment")),
    "electric_piano": ("fur_elise", 0, ("melody", "accompaniment")),
    "organ": ("ode_to_joy", 0, ("melody", "alto", "tenor", "bass")),
    "harpsichord": ("turkish_march", 0, ("melody", "inner", "accompaniment")),
    "clarinet": ("greensleeves", -12, ("melody",)),
    "saxophone": ("ode_to_joy", -12, ("melody",)),
    "bassoon": ("cello_prelude", 0, ("melody",)),
    "trombone": ("ode_to_joy", -12, ("melody",)),
    "french_horn": ("ode_to_joy", -12, ("melody",)),
    "tuba": ("ode_to_joy", -24, ("melody",)),
    "marimba": ("turkish_march", -12, ("melody",)),
    "xylophone": ("turkish_march", 0, ("melody",)),
    "vibraphone": ("fur_elise", -12, ("melody",)),
    "bell": ("ode_to_joy", 12, ("melody",)),
    "timpani": ("ode_to_joy", -24, ("melody",)),
    "sine": ("greensleeves", 0, ("melody",)),
    "triangle": ("fur_elise", 0, ("melody",)),
    "pluck": ("turkish_march", 0, ("melody",)),
    "bass": ("cello_prelude", -12, ("melody",)),
    "pad": ("ode_to_joy", 0, ("melody", "alto", "tenor", "bass")),
    "synthesizer": ("turkish_march", -12, ("melody",)),
    "theremin": ("greensleeves", 0, ("melody",)),
}

# (source part, instrument, transposition, gain, pan)
ENSEMBLES = {
    "violin": (
        "greensleeves",
        "String trio",
        (
            ("melody", "violin", 0, 0.85, -0.15),
            ("inner", "viola", 0, 0.40, 0.30),
            ("inner", "cello", -12, 0.45, 0.10),
        ),
    ),
    "flute": (
        "greensleeves",
        "Flute & harp",
        (
            ("melody", "flute", 0, 0.66, -0.18),
            ("inner", "harp", 0, 0.95, 0.25),
        ),
    ),
    "oboe": (
        "ode_to_joy",
        "Woodwind quartet",
        (
            ("melody", "oboe", 0, 0.85, -0.20),
            ("alto", "flute", 12, 0.40, 0.20),
            ("tenor", "clarinet", 0, 0.48, -0.35),
            ("bass", "bassoon", -12, 0.55, 0.35),
        ),
    ),
    "trumpet": (
        "ode_to_joy",
        "Brass quartet",
        (
            ("melody", "trumpet", 0, 0.80, -0.15),
            ("alto", "french_horn", 0, 0.48, 0.30),
            ("tenor", "trombone", -12, 0.55, -0.30),
            ("bass", "tuba", -12, 0.62, 0.15),
        ),
    ),
    "glockenspiel": (
        "fur_elise",
        "Glockenspiel & piano",
        (
            ("melody", "glockenspiel", 12, 0.66, -0.15),
            ("accompaniment", "piano", 0, 0.78, 0.20),
        ),
    ),
}

PERCUSSION = {
    "kick",
    "snare",
    "hat",
    "toms",
    "cymbal",
    "congas",
    "bongos",
    "tambourine",
    "drum_machine",
}
RINGING = {
    "guitar",
    "electric_guitar",
    "harp",
    "piano",
    "electric_piano",
    "marimba",
    "vibraphone",
    "glockenspiel",
    "bell",
    "pluck",
    "harpsichord",
    "mandolin",
    "kalimba",
    "celesta",
}


def performance_settings(voice: str) -> dict:
    """Conservative dry-demo controls and note-off space for each voice family."""
    info = get_instrument(voice)
    controls = {"brightness": 0.46}
    release = 0.06
    if info.family == "plucked_strings" or voice == "harpsichord":
        controls.update(decay_seconds=2.1, pluck_position=0.22)
        release = 0.13
    elif info.family == "bowed_strings":
        controls.update(vibrato_depth_cents=7, vibrato_rate_hz=4.8)
        release = 0.07
    elif info.family in {"woodwinds", "brass"}:
        controls.update(breath=0.055, vibrato_depth_cents=3, vibrato_rate_hz=4.7)
        release = 0.045
    elif info.family == "pitched_percussion":
        controls.update(decay_seconds=2.3)
        release = 0.19
    elif voice in {"piano", "electric_piano"}:
        controls.update(decay_seconds=2.5)
        release = 0.16
    overrides = {
        "mandolin": ({"decay_seconds": 1.8, "detune_cents": 5}, 0.11),
        "kalimba": ({"brightness": 0.5, "decay_seconds": 2.1}, 0.16),
        "celesta": ({"brightness": 0.4, "decay_seconds": 3.1}, 0.21),
        "recorder": ({"breath": 0.045, "vibrato_depth_cents": 0}, 0.04),
        "bass_guitar": ({"brightness": 0.34, "decay_seconds": 1.3}, 0.08),
        "glockenspiel": ({"brightness": 0.4, "decay_seconds": 2.5}, 0.22),
        "theremin": ({"brightness": 0.4, "vibrato_depth_cents": 7, "vibrato_rate_hz": 4.7}, 0.08),
    }
    if voice in overrides:
        values, release = overrides[voice]
        controls.update(values)
    controls = {key: value for key, value in controls.items() if key in info.tone_controls}
    return {"tone": Tone(**controls) if controls else None, "release_seconds": release}


@lru_cache(maxsize=1)
def pieces() -> dict:
    return json.loads(
        Path(__file__).with_name("music").joinpath("excerpts.json").read_text(encoding="utf-8")
    )


def arranged_notes(rows: list, instrument: str, transpose: int, end: float) -> list[Note]:
    # Collapse duplicated unisons when arranging several source voices on one
    # keyboard. Keep the longest held duration, then gate before a repeated key.
    merged: dict[tuple[float, int], float] = {}
    for pitch, start, duration in rows:
        key = (start, pitch + transpose)
        merged[key] = max(merged.get(key, 0), duration)
    events = sorted((start, pitch, duration) for (start, pitch), duration in merged.items())
    next_onset: dict[int, float] = {}
    result = []
    for start, pitch, duration in reversed(events):
        ringing = instrument in RINGING
        # Short release envelopes supply the ring-out; long written gates would
        # blur fast runs and hide the instrument's attack. Winds leave breath space.
        gate = 1.10 if ringing else 0.94
        if get_instrument(instrument).family == "bowed_strings":
            gate = 0.985
        length = duration * gate
        length = min(length, next_onset.get(pitch, end) - start - 0.006, end - start)
        # Shaped dynamics are intentional arrangement decisions, not randomness.
        accent = 0.05 if start % 4 < 0.01 else 0
        phrase = 0.055 * math.sin(start * math.pi / 8) - 0.025 * (start / max(end, 1))
        result.append(
            Note(
                pitch=pitch,
                start=start,
                duration=max(0.005, length),
                velocity=0.72 + accent + phrase,
            )
        )
        next_onset[pitch] = start
    return list(reversed(result))


def percussion_notes(instrument: str, beats: int) -> list[Note]:
    patterns = {
        "kick": [(0, 0.9), (2, 0.78)],
        "snare": [(1, 0.85), (3, 0.9), (3.75, 0.38)],
        "hat": [(i / 2, 0.8 if i % 2 == 0 else 0.48) for i in range(8)],
        "toms": [(0, 0.85), (1.5, 0.58), (2.5, 0.72), (3.5, 0.62)],
        "cymbal": [(0, 0.85)],
        "congas": [(0, 0.88), (1.5, 0.56), (2, 0.78), (3, 0.52), (3.5, 0.65)],
        "bongos": [(0, 0.80), (0.75, 0.45), (1.5, 0.65), (2, 0.84), (3, 0.60)],
        "tambourine": [(1, 0.76), (3, 0.9)],
    }
    if instrument == "drum_machine":
        return sorted(
            (note for voice in ("kick", "snare", "hat") for note in percussion_notes(voice, beats)),
            key=lambda n: n.start,
        )
    pitch = get_instrument(instrument).midi_note
    duration = {"kick": 0.7, "snare": 0.35, "hat": 0.17, "cymbal": 3.8, "tambourine": 0.8}.get(
        instrument, 0.4
    )
    return [
        Note(pitch=pitch, start=bar + offset, duration=duration, velocity=velocity)
        for bar in range(0, beats, 4)
        for offset, velocity in patterns[instrument]
    ]


def music_score(instrument: InstrumentInfo) -> tuple[Song, dict]:
    """Build one clearly credited musical example featuring the requested voice."""
    if instrument.id in PERCUSSION:
        key = "ode_to_joy"
        piece = pieces()[key]
        setup = "Melody with featured percussion"
        # Keep the supporting bass from masking quieter, short metal/noise voices.
        # These levels were checked on these arrangements, not globally fitted.
        piano_gain, bass_gain = 0.52, 0.22
        if instrument.id in {"hat", "tambourine"}:
            piano_gain, bass_gain = 0.12, 0.06
        elif instrument.id in {"snare", "cymbal"}:
            piano_gain, bass_gain = 0.25, 0.18
        plans = [
            ("melody", "piano", 0, piano_gain, -0.20),
            ("bass", "bass_guitar", -12, bass_gain, 0.20),
        ]
    elif instrument.id in ENSEMBLES:
        key, setup, plans = ENSEMBLES[instrument.id]
        piece = pieces()[key]
    else:
        key, transpose, parts = SOLOS[instrument.id]
        piece = pieces()[key]
        setup = "Solo arrangement"
        plans = [(parts, instrument.id, transpose, 0.88, 0)]
    end = piece["beats"] + 0.75
    tracks = []
    if instrument.id in PERCUSSION:
        tracks.append(
            Track(
                name=instrument.name,
                instrument=instrument.id,
                gain=0.95,
                notes=percussion_notes(instrument.id, piece["beats"]),
            )
        )
    for parts, voice, transpose, gain, pan in plans:
        parts = (parts,) if isinstance(parts, str) else parts
        rows = [row for part in parts for row in piece["parts"].get(part, [])]
        tracks.append(
            Track(
                name=get_instrument(voice).name,
                instrument=voice,
                gain=gain,
                pan=pan,
                notes=arranged_notes(rows, voice, transpose, piece["beats"]),
                **performance_settings(voice),
            )
        )
    if instrument.id == "timpani":
        setup = "Melodic study · freely retuned timpani"
    song = Song(
        title=f"{piece['title']} / {instrument.name}",
        bpm=piece["bpm"],
        beats=end,
        sample_rate=44100,
        seed=2026,
        tracks=tracks,
    )
    metadata = {
        "title": piece["title"],
        "composer": piece["composer"],
        "arrangement": setup,
        "performers": ", ".join(get_instrument(t.instrument).name for t in tracks),
        "source": piece["source_url"],
        "credit": piece["credit"],
        "license": piece["license"],
        "piece": key,
        "excerpt": True,
        "complete": False,
        "source_beats": piece["beats"],
        "performance_notes": "Dry procedural arrangement with shaped dynamics and short releases; "
        "octaves and articulation are adapted for the featured voice.",
    }
    return song, metadata
