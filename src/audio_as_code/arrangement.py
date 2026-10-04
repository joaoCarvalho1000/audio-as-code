"""Tempo-aware cues, named score sections, and measured loop previews."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from ._audio import _metrics
from .effects import effects_tail
from .model import Note, Song, Track
from .pattern import Pattern
from .render import RenderResult, render_audio


def _finite(value: float, name: str, *, positive: bool = False) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (value <= 0 if positive else value < 0)
    ):
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{name} must be a finite {qualifier} number")


def beat_at_seconds(song: Song, seconds: float) -> float:
    """Invert a score's step tempo map within its musical duration.

    The returned beat is continuous. Audio export rounds it to the nearest sample.
    """
    _finite(seconds, "seconds")
    if seconds > song.seconds:
        raise ValueError("seconds exceeds the song's musical duration")
    previous_beat, elapsed, bpm = 0.0, 0.0, song.bpm
    for change in song.tempo_map:
        boundary = elapsed + (change.beat - previous_beat) * 60 / bpm
        if seconds <= boundary:
            return previous_beat + (seconds - elapsed) * bpm / 60
        previous_beat, elapsed, bpm = change.beat, boundary, change.bpm
    return min(song.beats, previous_beat + (seconds - elapsed) * bpm / 60)


def place_at_seconds(song: Song, pattern: Pattern, seconds: float) -> tuple[Note, ...]:
    """Place a phrase's first beat at a requested time, rejecting score overflow."""
    if not isinstance(pattern, Pattern):
        raise ValueError("pattern must be a Pattern")
    beat = beat_at_seconds(song, seconds)
    if beat + pattern.beats > song.beats + 1e-9:
        raise ValueError("pattern extends beyond the song's musical duration")
    return pattern.at(beat)


@dataclass(frozen=True)
class Section:
    """A named half-open interval [start_beat, end_beat) on a score."""

    name: str
    start_beat: float
    end_beat: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("section name must contain a visible character")
        _finite(self.start_beat, "start_beat")
        _finite(self.end_beat, "end_beat", positive=True)
        if self.end_beat <= self.start_beat:
            raise ValueError("section end_beat must exceed start_beat")

    @property
    def beats(self) -> float:
        return self.end_beat - self.start_beat


@dataclass(frozen=True)
class Arrangement:
    """Score plus nonoverlapping named sections kept outside score version 1."""

    song: Song
    sections: tuple[Section, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.song, Song):
            raise ValueError("song must be a Song")
        sections = tuple(self.sections)
        if any(not isinstance(section, Section) for section in sections):
            raise ValueError("sections must contain Section instances")
        if len({section.name for section in sections}) != len(sections):
            raise ValueError("section names must be unique")
        ordered = sorted(sections, key=lambda section: section.start_beat)
        if any(section.end_beat > self.song.beats + 1e-9 for section in ordered):
            raise ValueError("section extends beyond the song")
        if any(
            left.end_beat > right.start_beat
            for left, right in zip(ordered, ordered[1:], strict=False)
        ):
            raise ValueError("sections must not overlap")
        object.__setattr__(self, "sections", sections)

    def section(self, name: str) -> Section:
        for section in self.sections:
            if section.name == name:
                return section
        raise ValueError(f"unknown section {name!r}")

    def replace_section(self, name: str, replacements: Mapping[str, Pattern]) -> Arrangement:
        """Replace notes on named tracks inside a section without altering other score data.

        Edited tracks must have chronological note starts. Notes crossing either
        boundary are rejected; a section edit never clips or splits a note.
        Tracks and notes outside the edit keep their order. When the replacement
        changes note count, later note indices (and their render seeds) shift.
        """
        section = self.section(name)
        if not isinstance(replacements, Mapping) or not replacements:
            raise ValueError("replacements must map track names to Patterns")
        if any(not isinstance(track_name, str) for track_name in replacements):
            raise ValueError("replacements must map track names to Patterns")
        track_names = {track.name for track in self.song.tracks}
        if set(replacements) - track_names:
            raise ValueError(f"unknown tracks: {sorted(set(replacements) - track_names)}")
        for track_name, pattern in replacements.items():
            if not isinstance(pattern, Pattern):
                raise ValueError("replacements must map track names to Patterns")
            if not math.isclose(pattern.beats, section.beats, rel_tol=0, abs_tol=1e-9):
                raise ValueError("replacement pattern length must equal section length")
            if any(
                a.start > b.start for a, b in zip(pattern.notes, pattern.notes[1:], strict=False)
            ):
                raise ValueError(f"replacement for {track_name!r} must have chronological notes")
        tracks = []
        for track in self.song.tracks:
            if track.name not in replacements:
                tracks.append(track)
                continue
            if any(a.start > b.start for a, b in zip(track.notes, track.notes[1:], strict=False)):
                raise ValueError(f"track {track.name!r} notes must have chronological starts")
            before, after = [], []
            for note in track.notes:
                end = note.start + note.duration
                if note.start < section.start_beat:
                    if end > section.start_beat + 1e-9:
                        raise ValueError(f"track {track.name!r} has a note crossing section start")
                    before.append(note)
                elif note.start < section.end_beat:
                    if end > section.end_beat + 1e-9:
                        raise ValueError(f"track {track.name!r} has a note crossing section end")
                else:
                    after.append(note)
            placed = replacements[track.name].at(section.start_beat)
            tracks.append(
                Track.model_validate({**track.model_dump(), "notes": before + list(placed) + after})
            )
        return Arrangement(
            Song.model_validate({**self.song.model_dump(), "tracks": tracks}), self.sections
        )


@dataclass(frozen=True)
class LoopRegion:
    """A half-open musical region; audio frames use rounded boundary seconds."""

    start_beat: float
    end_beat: float

    def __post_init__(self) -> None:
        _finite(self.start_beat, "start_beat")
        _finite(self.end_beat, "end_beat", positive=True)
        if self.end_beat <= self.start_beat:
            raise ValueError("loop end_beat must exceed start_beat")


def render_loop_preview(
    song: Song, region: LoopRegion, *, repetitions: int = 2, allow_tail_crop: bool = False
) -> RenderResult:
    """Repeat rendered region samples and measure its joins; no seam processing.

    Render the full song first so note seeds and processing match normal playback.
    By default, reject notes/releases/effect tails that cross either boundary.
    Set allow_tail_crop explicitly to audition a crop and inspect the report.
    """
    if not isinstance(region, LoopRegion):
        raise ValueError("region must be a LoopRegion")
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 2:
        raise ValueError("repetitions must be an integer of at least 2")
    if not isinstance(allow_tail_crop, bool):
        raise ValueError("allow_tail_crop must be a boolean")
    if region.end_beat > song.beats + 1e-9:
        raise ValueError("loop region extends beyond the song")
    start_seconds = song.beat_to_seconds(region.start_beat)
    end_seconds = song.beat_to_seconds(region.end_beat)
    start_frame = round(start_seconds * song.sample_rate)
    end_frame = round(end_seconds * song.sample_rate)
    frames = end_frame - start_frame
    if frames < 1:
        raise ValueError("loop region is shorter than one audio sample")
    if frames * repetitions > 300 * song.sample_rate:
        raise ValueError("repeated loop preview exceeds the five-minute render limit")
    # Conservative tail estimate: any note or generated effect still active at a
    # boundary can make the first/next cycle depend on context outside this crop.
    effect_tail = effects_tail(song.effects)
    crossing_start = False
    latest_end = start_seconds
    for track in song.tracks:
        track_tail = effects_tail(track.effects) + effect_tail
        for note in track.notes:
            onset = song.beat_to_seconds(note.start)
            audible_end = (
                song.beat_to_seconds(song.note_gate_end(track, note))
                + song.note_release_seconds(track, note)
                + track_tail
            )
            if onset < start_seconds and audible_end > start_seconds + 1e-9:
                crossing_start = True
            if onset < end_seconds and audible_end > latest_end:
                latest_end = audible_end
    crossing_end_seconds = max(0.0, latest_end - end_seconds)
    if not allow_tail_crop and (crossing_start or crossing_end_seconds > 1e-9):
        raise ValueError("notes or effect tails cross a loop boundary; pass allow_tail_crop=True")
    source = render_audio(song)
    cycle = source.audio[start_frame:end_frame]
    repeated = np.tile(cycle, (repetitions, 1))
    jump = float(np.max(np.abs(cycle[0] - cycle[-1])))
    adjacent = float(np.max(np.abs(np.diff(cycle, axis=0)))) if frames > 1 else 0.0
    report = {
        **source.report,
        "audio": _metrics(repeated, song.sample_rate),
        "loop": {
            "start_beat": region.start_beat,
            "end_beat": region.end_beat,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "cycle_frames": frames,
            "repetitions": repetitions,
            "preview_frames": len(repeated),
            "cycle_seconds": frames / song.sample_rate,
            "preview_seconds": len(repeated) / song.sample_rate,
            "boundary_jump": jump,
            "largest_inner_step": adjacent,
            "tail_crosses_start": crossing_start,
            "estimated_tail_past_end_seconds": crossing_end_seconds,
            "tail_crop_allowed": allow_tail_crop,
            "source_audio": source.report["audio"],
        },
    }
    return RenderResult(repeated, report)
