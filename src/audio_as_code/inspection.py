"""Read-only score measurements and static export checks, without synthesizing audio."""

from __future__ import annotations

from .effects import effects_tail
from .instruments import DRUM_NOTES, get_instrument
from .midi import TICKS_PER_BEAT
from .model import Song, Track, midi_pitch
from .render import MAX_RENDER_SECONDS


def _issue(
    issues: list[dict], code: str, target: str, path: list, message: str, *, blocking: bool = False
) -> None:
    issues.append(
        {
            "code": code,
            "severity": "error" if blocking else "warning",
            "target": target,
            "path": path,
            "message": message,
        }
    )


def _polyphony(intervals: list[tuple[float, float]]) -> int:
    events = [event for start, end in intervals if end > start for event in ((start, 1), (end, -1))]
    active = peak = 0
    for _, change in sorted(events):
        active += change
        peak = max(peak, active)
    return peak


def _range(values: list[int]) -> dict | None:
    return {"min": min(values), "max": max(values)} if values else None


def _export_pitch(track: Track, pitch: int | str) -> int:
    if track.instrument in DRUM_NOTES and track.instrument != "drum_machine":
        return DRUM_NOTES[track.instrument]
    return midi_pitch(pitch)


def _midi_issues(song: Song, issues: list[dict]) -> int:
    melodic_count = sum(track.instrument not in DRUM_NOTES for track in song.tracks)
    if melodic_count > 15:
        _issue(
            issues,
            "midi_melodic_channel_limit",
            "midi",
            ["tracks"],
            "MIDI supports at most 15 melodic tracks; empty and muted tracks also count.",
            blocking=True,
        )
    end_tick = round(song.beats * TICKS_PER_BEAT)
    if not 1 <= end_tick <= 0x0FFFFFFF:
        _issue(
            issues,
            "midi_duration_out_of_range",
            "midi",
            ["beats"],
            "Song duration cannot be represented on the MIDI tick grid.",
            blocking=True,
        )
    drum_kinds: set[str] = set()
    percussion: dict[int, list[tuple[int, int, int, int]]] = {}
    for track_index, track in enumerate(song.tracks):
        path = ["tracks", track_index]
        is_drum = track.instrument in DRUM_NOTES
        if is_drum:
            if track.instrument in drum_kinds:
                _issue(
                    issues,
                    "midi_duplicate_drum_instrument",
                    "midi",
                    [*path, "instrument"],
                    "MIDI requires at most one track per drum instrument.",
                    blocking=True,
                )
            drum_kinds.add(track.instrument)
            _issue(
                issues,
                "midi_shared_percussion_channel",
                "midi",
                path,
                "Percussion shares channel 10; gain is encoded in velocity, per-track pan "
                "is omitted, and events are grouped in the first percussion track.",
            )
        note_ends: dict[int, int] = {}
        if track.pedal:
            _issue(
                issues,
                "midi_pedal_receiver_behavior",
                "midi",
                [*path, "pedal"],
                "Binary piano pedal is exported as CC64; open pedal lifts at score end. "
                "Damper tails and repeated-pitch behavior depend on the receiving synthesizer.",
            )
            if any(
                round(event.beat * TICKS_PER_BEAT) / TICKS_PER_BEAT != event.beat
                for event in track.pedal
            ):
                _issue(
                    issues,
                    "midi_pedal_timing_quantized",
                    "midi",
                    [*path, "pedal"],
                    "Some pedal events move or collapse together on the 480-tick MIDI grid.",
                )
        quantized = False
        for note_index, note in sorted(enumerate(track.notes), key=lambda item: item[1].start):
            pitch = _export_pitch(track, note.pitch)
            start = round(note.start * TICKS_PER_BEAT)
            end = min(end_tick, round((note.start + note.duration) * TICKS_PER_BEAT))
            note_path = [*path, "notes", note_index]
            quantized |= (
                start / TICKS_PER_BEAT != note.start
                or end / TICKS_PER_BEAT != note.start + note.duration
            )
            if end <= start:
                _issue(
                    issues,
                    "midi_note_below_tick",
                    "midi",
                    note_path,
                    "Note has no positive duration after MIDI tick rounding.",
                    blocking=True,
                )
            if start < note_ends.get(pitch, 0):
                _issue(
                    issues,
                    "midi_same_pitch_overlap",
                    "midi",
                    note_path,
                    f"MIDI pitch {pitch} overlaps an earlier note on this track.",
                    blocking=True,
                )
            note_ends[pitch] = max(end, note_ends.get(pitch, 0))
            if is_drum and track.gain and song.master_gain and end > start:
                percussion.setdefault(pitch, []).append((start, end, track_index, note_index))
        if quantized:
            _issue(
                issues,
                "midi_note_timing_quantized",
                "midi",
                [*path, "notes"],
                "Some note boundaries change on the 480-tick-per-beat MIDI grid.",
            )
        if track.tone is not None:
            _issue(
                issues,
                "midi_tone_not_exported",
                "midi",
                [*path, "tone"],
                "Instrument tone controls are not exported to MIDI.",
            )
        if track.release_seconds or any(note.release_seconds for note in track.notes):
            _issue(
                issues,
                "midi_releases_not_exported",
                "midi",
                path,
                "Note releases and audio tails are not exported; MIDI uses written durations.",
            )
    for pitch, intervals in sorted(percussion.items()):
        previous_end, previous_track = 0, -1
        for start, end, track_index, note_index in sorted(intervals):
            if start < previous_end and track_index != previous_track:
                _issue(
                    issues,
                    "midi_percussion_pitch_overlap",
                    "midi",
                    ["tracks", track_index, "notes", note_index],
                    f"Percussion MIDI pitch {pitch} overlaps track {previous_track} "
                    "on shared channel 10.",
                    blocking=True,
                )
            if end > previous_end:
                previous_end, previous_track = end, track_index
    for path, owner in [([], song), *[(["tracks", i], t) for i, t in enumerate(song.tracks)]]:
        if owner.automation:
            _issue(
                issues,
                "midi_automation_not_exported",
                "midi",
                [*path, "automation"],
                "MIDI uses static gain and pan; automation is not exported.",
            )
        if owner.effects:
            _issue(
                issues,
                "midi_effects_not_exported",
                "midi",
                [*path, "effects"],
                "Procedural effects and their audio tails are not exported to MIDI.",
            )
    if any(
        round(change.beat * TICKS_PER_BEAT) / TICKS_PER_BEAT != change.beat
        for change in song.tempo_map
    ):
        _issue(
            issues,
            "midi_tempo_timing_quantized",
            "midi",
            ["tempo_map"],
            "Some tempo changes move on the 480-tick-per-beat MIDI grid.",
        )
    return melodic_count


def inspect_score(song: Song) -> dict:
    """Return deterministic JSON-safe score facts and static render/MIDI readiness.

    Invalid models raise Pydantic ValidationError, including unchecked model copies.
    Readiness means the documented static checks pass, not that output quality,
    runtime resources, or destination permissions have been established.
    """
    song = Song.model_validate(song.model_dump())
    issues: list[dict] = []
    duration = song.seconds
    render_duration = song.render_seconds
    frames = round(render_duration * song.sample_rate)
    if render_duration > MAX_RENDER_SECONDS:
        _issue(
            issues,
            "render_duration_limit",
            "render",
            [],
            f"Render duration including releases and effects exceeds {MAX_RENDER_SECONDS} seconds.",
            blocking=True,
        )
    if frames < 1:
        _issue(
            issues,
            "render_below_one_sample",
            "render",
            ["beats"],
            "Song duration rounds to fewer than one audio sample.",
            blocking=True,
        )
    tracks = []
    all_intervals = []
    for track_index, track in enumerate(song.tracks):
        instrument = get_instrument(track.instrument)
        intervals = [(note.start, note.start + note.duration) for note in track.notes]
        all_intervals.extend(intervals)
        starts = [start for start, _ in intervals]
        ends = [end for _, end in intervals]
        dry_end = max(
            (
                song.beat_to_seconds(song.note_gate_end(track, note))
                + song.note_release_seconds(track, note)
                for note in track.notes
            ),
            default=0.0,
        )
        if not track.notes:
            _issue(
                issues,
                "empty_track",
                "score",
                ["tracks", track_index, "notes"],
                "Track contains no notes.",
            )
        for note_index, note in enumerate(track.notes):
            if song.tempo_map:
                start_frame = round(song.beat_to_seconds(note.start) * song.sample_rate)
                end_frame = round(
                    song.beat_to_seconds(song.note_gate_end(track, note)) * song.sample_rate
                )
            else:
                samples_per_beat = song.sample_rate * 60 / song.bpm
                start_frame = round(note.start * samples_per_beat)
                end_frame = round(song.note_gate_end(track, note) * samples_per_beat)
            if end_frame <= start_frame:
                _issue(
                    issues,
                    "render_note_below_sample",
                    "render",
                    ["tracks", track_index, "notes", note_index],
                    "Renderer skips this note because its held duration rounds to zero samples.",
                )
        tracks.append(
            {
                "index": track_index,
                "name": track.name,
                "instrument": track.instrument,
                "family": instrument.family,
                "engine": instrument.engine,
                "instrument_description": instrument.description,
                "note_count": len(track.notes),
                "pedal_event_count": len(track.pedal),
                "pedal_auto_lift": bool(track.pedal and track.pedal[-1].down),
                "pedal_sustained_note_count": sum(
                    song.note_gate_end(track, note) > note.start + note.duration
                    for note in track.notes
                ),
                "written_pitch_range": _range([midi_pitch(note.pitch) for note in track.notes]),
                "midi_pitch_range": _range(
                    [_export_pitch(track, note.pitch) for note in track.notes]
                ),
                "first_note_beat": min(starts) if starts else None,
                "last_note_end_beat": max(ends) if ends else None,
                "first_note_seconds": song.beat_to_seconds(min(starts)) if starts else None,
                "last_note_end_seconds": song.beat_to_seconds(max(ends)) if ends else None,
                "dry_end_seconds": dry_end,
                "effect_end_seconds": dry_end + effects_tail(track.effects),
                "max_note_polyphony": _polyphony(intervals),
                "midi_percussion": track.instrument in DRUM_NOTES,
            }
        )
    melodic_count = _midi_issues(song, issues)
    return {
        "inspection_version": "1",
        "validation": {"valid": True, "schema_version": song.schema_version},
        "summary": {
            "title": song.title,
            "bpm": song.bpm,
            "beats": song.beats,
            "sample_rate": song.sample_rate,
            "seed": song.seed,
            "track_count": len(tracks),
            "note_count": sum(track["note_count"] for track in tracks),
            "max_note_polyphony": _polyphony(all_intervals),
            "duration_seconds": duration,
            "render_duration_seconds": render_duration,
            "tail_seconds": max(0.0, render_duration - duration),
        },
        "tracks": tracks,
        "readiness": {
            "render": {
                "ready": not any(
                    i["target"] == "render" and i["severity"] == "error" for i in issues
                ),
                "duration_limit_seconds": MAX_RENDER_SECONDS,
                "frames": frames,
            },
            "midi": {
                "ready": not any(
                    i["target"] == "midi" and i["severity"] == "error" for i in issues
                ),
                "melodic_tracks": melodic_count,
                "melodic_track_limit": 15,
                "ticks_per_beat": TICKS_PER_BEAT,
            },
        },
        "issues": issues,
        "limitations": [
            "Readiness covers static score checks only; no audio or MIDI is generated, "
            "and runtime resources and output paths are not checked.",
            "Polyphony counts written half-open note intervals, including muted notes; "
            "it excludes pedal sustain, releases and effects and does not estimate CPU use "
            "or audible voices.",
            "Piano pedal extends independent note gates until lift; this damper approximation "
            "does not model half-pedaling, sympathetic resonance, or repedaling released tails.",
            "Timing and tail horizons follow score rules, not measured audible duration. "
            "No loudness, clipping, tuning, musical quality, or perceptual realism is measured.",
            "MIDI preserves notes and tempo with tick rounding; sounds depend on the receiving "
            "synthesizer and do not reproduce the procedural audio voices.",
        ],
    }
