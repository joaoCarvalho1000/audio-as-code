"""Shared output limits and event mapping for inspection and exporters."""

from __future__ import annotations

from .instruments import DRUM_NOTES
from .model import Note, Song, Track, midi_pitch

MAX_RENDER_SECONDS = 300
TICKS_PER_BEAT = 480
MAX_MIDI_TICK = 0x0FFFFFFF
MAX_MELODIC_TRACKS = 15


def note_frame(song: Song, beat: float) -> int:
    # Retain the original arithmetic order on legacy rounding boundaries.
    if not song.tempo_map:
        return round(beat * (song.sample_rate * 60 / song.bpm))
    return round(song.beat_to_seconds(beat) * song.sample_rate)


def midi_tick(beat: float) -> int:
    return round(beat * TICKS_PER_BEAT)


def midi_note_ticks(note: Note, end_tick: int) -> tuple[int, int]:
    return midi_tick(note.start), min(end_tick, midi_tick(note.start + note.duration))


def midi_export_pitch(track: Track, pitch: int | str) -> int:
    if track.instrument in DRUM_NOTES and track.instrument != "drum_machine":
        return DRUM_NOTES[track.instrument]
    return midi_pitch(pitch)
