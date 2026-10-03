"""Small, explicit composition helpers; no DSL or code evaluation required."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .model import Note, midi_pitch

Step = int | str | Sequence[int | str] | None


def _positive(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")


def _nonnegative(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")


@dataclass(frozen=True)
class Pattern:
    """An immutable phrase with explicit length, including trailing rests."""

    notes: tuple[Note, ...]
    beats: float

    def __post_init__(self) -> None:
        _positive(self.beats, "beats")
        object.__setattr__(self, "notes", tuple(self.notes))
        for note in self.notes:
            if not isinstance(note, Note):
                raise ValueError("pattern notes must be Note instances")
            if note.start + note.duration > self.beats + 1e-9:
                raise ValueError("pattern notes must fit inside its length")

    @classmethod
    def sequence(
        cls, steps: Sequence[Step], *, step: float = 1, gate: float = 0.8, velocity: float = 0.8
    ) -> Pattern:
        """One pitch/chord/rest per step. None is a rest; a list/tuple is a chord."""
        if (
            not isinstance(steps, Sequence)
            or isinstance(steps, (str, bytes, bytearray))
            or not steps
        ):
            raise ValueError("steps must be a nonempty sequence of pitches, chords, or None")
        _positive(step, "step")
        _positive(gate, "gate")
        if gate > 1:
            raise ValueError("gate must be at most 1")
        # Validate even when every step is a rest.
        Note(velocity=velocity)
        notes = []
        for index, item in enumerate(steps):
            if item is None:
                continue
            if not isinstance(item, (int, str)) and (
                not isinstance(item, Sequence) or isinstance(item, (bytes, bytearray))
            ):
                raise ValueError("each step must be a pitch, a sequence of pitches, or None")
            pitches = [item] if isinstance(item, (int, str)) else item
            for pitch in pitches:
                notes.append(
                    Note(pitch=pitch, start=index * step, duration=step * gate, velocity=velocity)
                )
        return cls(tuple(notes), len(steps) * step)

    def repeat(self, times: int) -> Pattern:
        if isinstance(times, bool) or not isinstance(times, int) or times < 1:
            raise ValueError("times must be a positive integer")
        return Pattern(
            tuple(note for index in range(times) for note in self.at(index * self.beats)),
            self.beats * times,
        )

    def transpose(self, semitones: int) -> Pattern:
        if isinstance(semitones, bool) or not isinstance(semitones, int):
            raise ValueError("semitones must be an integer")
        return Pattern(
            tuple(
                Note(**{**note.model_dump(), "pitch": midi_pitch(note.pitch) + semitones})
                for note in self.notes
            ),
            self.beats,
        )

    def then(self, other: Pattern) -> Pattern:
        """Append another phrase after this phrase's full length, including rests."""
        if not isinstance(other, Pattern):
            raise ValueError("other must be a Pattern")
        return Pattern(self.notes + other.at(self.beats), self.beats + other.beats)

    def overlay(self, other: Pattern, *, offset: float = 0) -> Pattern:
        """Layer a phrase at a nonnegative offset; retain both full phrase lengths.

        Notes remain in this phrase's order followed by the placed layer's order.
        Overlapping and identical notes are retained; no mixing or deduplication occurs.
        """
        if not isinstance(other, Pattern):
            raise ValueError("other must be a Pattern")
        _nonnegative(offset, "offset")
        return Pattern(self.notes + other.at(offset), max(self.beats, offset + other.beats))

    def stretch(self, factor: float) -> Pattern:
        """Scale beat positions, durations, and phrase length by a positive factor.

        A factor of 2 doubles the phrase length. Release times stay in seconds.
        """
        _positive(factor, "factor")
        return Pattern(
            tuple(
                Note(
                    **{
                        **note.model_dump(),
                        "start": note.start * factor,
                        "duration": note.duration * factor,
                    }
                )
                for note in self.notes
            ),
            self.beats * factor,
        )

    def scale_velocity(self, factor: float) -> Pattern:
        """Multiply velocities by a positive factor, requiring results in (0, 1].

        Values above 1 raise ValueError rather than clipping away relative accents.
        """
        _positive(factor, "factor")
        return Pattern(
            tuple(
                Note(**{**note.model_dump(), "velocity": note.velocity * factor})
                for note in self.notes
            ),
            self.beats,
        )

    def at(self, beat: float) -> tuple[Note, ...]:
        """Place a phrase on the score's absolute timeline."""
        _nonnegative(beat, "beat")
        return tuple(
            Note(**{**note.model_dump(), "start": note.start + beat}) for note in self.notes
        )
