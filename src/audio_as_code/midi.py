"""Standard MIDI type-1 export with tempo, programs, pan, and percussion mapping."""

from __future__ import annotations

from pathlib import Path

import mido

from .instruments import DRUM_NOTES, PROGRAMS
from .model import Song, midi_pitch

TICKS_PER_BEAT = 480


def _export_warnings(song: Song) -> list[str]:
    messages = ["MIDI preserves notes and tempo; sounds depend on the receiving synthesizer."]
    if any(track.instrument in DRUM_NOTES for track in song.tracks):
        messages.append(
            "Percussion uses shared channel 10, with gain in velocity and no per-track pan. "
            "Percussion note events are grouped in the first percussion track; "
            "other percussion track names are retained as metadata."
        )
    if any(track.tone is not None for track in song.tracks):
        messages.append("Instrument tone controls are not exported.")
    if song.tempo_map:
        messages.append("Tempo changes are rounded to the 480-tick beat grid.")
    if any(track.pedal for track in song.tracks):
        messages.append(
            "Piano pedal events use binary CC64 on the 480-tick beat grid; an open pedal "
            "lifts at score end. Damper tails and repeated-pitch behavior depend on the receiver."
        )
    if song.automation or any(track.automation for track in song.tracks):
        messages.append(
            "Gain/pan automation is not exported; MIDI uses static track/master gain and pan."
        )
    if song.effects or any(track.effects for track in song.tracks):
        messages.append("Procedural effects and their audio tails are not exported.")
    if any(
        track.release_seconds or any(note.release_seconds for note in track.notes)
        for track in song.tracks
    ):
        messages.append("Note releases are not exported; MIDI uses written note durations.")
    return [" ".join(messages)]


def export_midi(song: Song, path: str | Path) -> dict:
    song = Song.model_validate(song.model_dump())
    melodic = [track for track in song.tracks if track.instrument not in DRUM_NOTES]
    if len(melodic) > 15:
        raise ValueError(
            "MIDI export supports at most 15 melodic tracks (channel 10 is percussion)"
        )
    drum_kinds = [track.instrument for track in song.tracks if track.instrument in DRUM_NOTES]
    if len(set(drum_kinds)) != len(drum_kinds):
        raise ValueError("MIDI export requires at most one track per drum instrument")
    midi = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    end_tick = round(song.beats * TICKS_PER_BEAT)
    if end_tick < 1 or end_tick > 0x0FFFFFFF:
        raise ValueError("song duration cannot be represented on the MIDI tick grid")
    tempo = mido.MidiTrack()
    tempo.append(mido.MetaMessage("track_name", name="Tempo"))
    tempo.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.bpm)))
    previous_tempo_tick = 0
    for change in song.tempo_map:
        tick = round(change.beat * TICKS_PER_BEAT)
        tempo.append(
            mido.MetaMessage(
                "set_tempo", tempo=mido.bpm2tempo(change.bpm), time=tick - previous_tempo_tick
            )
        )
        previous_tempo_tick = tick
    tempo.append(mido.MetaMessage("end_of_track", time=end_tick - previous_tempo_tick))
    midi.tracks.append(tempo)
    channels = iter(channel for channel in range(16) if channel != 9)
    percussion_intervals: dict[int, list[tuple[int, int, str]]] = {}
    track_events = []
    percussion_events = None
    for track in song.tracks:
        percussion = track.instrument in DRUM_NOTES
        channel = 9 if percussion else next(channels)
        output = mido.MidiTrack()
        # UTF-8 metadata is explicitly selected for titles outside Latin-1.
        output.append(mido.MetaMessage("track_name", name=track.name))
        if not percussion:
            output.append(
                mido.Message("program_change", channel=channel, program=PROGRAMS[track.instrument])
            )
            output.append(
                mido.Message(
                    "control_change",
                    channel=channel,
                    control=7,
                    value=round(track.gain * song.master_gain * 127),
                )
            )
            output.append(
                mido.Message(
                    "control_change",
                    channel=channel,
                    control=10,
                    value=round((track.pan + 1) * 63.5),
                )
            )
        events = []
        for pedal in track.pedal:
            events.append(
                (
                    round(pedal.beat * TICKS_PER_BEAT),
                    -1,
                    mido.Message(
                        "control_change",
                        channel=channel,
                        control=64,
                        value=127 if pedal.down else 0,
                    ),
                )
            )
        if track.pedal and track.pedal[-1].down:
            events.append(
                (end_tick, -1, mido.Message("control_change", channel=channel, control=64, value=0))
            )
        note_ends: dict[int, int] = {}
        for note in sorted(track.notes, key=lambda note: note.start):
            pitch = (
                DRUM_NOTES[track.instrument]
                if percussion and track.instrument != "drum_machine"
                else midi_pitch(note.pitch)
            )
            start = round(note.start * TICKS_PER_BEAT)
            end = min(end_tick, round((note.start + note.duration) * TICKS_PER_BEAT))
            if end <= start:
                raise ValueError(
                    f"track {track.name!r}: note at beat {note.start} is shorter than one MIDI tick"
                )
            if start < note_ends.get(pitch, 0):
                raise ValueError(
                    f"track {track.name!r}: overlapping MIDI pitch {pitch}; "
                    "shorten or split the notes"
                )
            note_ends[pitch] = end
            if track.gain == 0 or song.master_gain == 0:
                continue
            if percussion:
                percussion_intervals.setdefault(pitch, []).append((start, end, track.name))
            velocity = note.velocity * (track.gain * song.master_gain if percussion else 1)
            velocity = max(1, round(velocity * 127))
            events.append(
                (start, 1, mido.Message("note_on", channel=channel, note=pitch, velocity=velocity))
            )
            events.append(
                (end, 0, mido.Message("note_off", channel=channel, note=pitch, velocity=0))
            )
        if percussion:
            # All percussion shares one channel. Sorting within separate MIDI tracks
            # cannot guarantee that a retrigger follows the previous track's note-off.
            if percussion_events is None:
                percussion_events = events
            else:
                percussion_events.extend(events)
                events = []
        track_events.append((output, events))
        midi.tracks.append(output)
    for pitch, intervals in percussion_intervals.items():
        previous_end = 0
        previous_track = ""
        for start, end, track_name in sorted(intervals):
            if start < previous_end:
                raise ValueError(
                    f"overlapping percussion MIDI pitch {pitch} across tracks "
                    f"{previous_track!r} and {track_name!r}; channel 10 is shared"
                )
            previous_end, previous_track = end, track_name
    for output, events in track_events:
        previous = 0
        # Pedal changes precede note-offs, then note-ons at the same tick.
        for tick, _, event in sorted(events, key=lambda item: (item[0], item[1])):
            output.append(event.copy(time=tick - previous))
            previous = tick
        output.append(mido.MetaMessage("end_of_track", time=end_tick - previous))
    midi.charset = "utf-8"
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    midi.save(str(destination))
    return {
        "output": str(destination),
        "tracks": len(song.tracks),
        "ticks_per_beat": TICKS_PER_BEAT,
        "duration_seconds": midi.length,
        "warnings": _export_warnings(song),
    }
