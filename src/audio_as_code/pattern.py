"""Small, explicit composition helpers; no DSL or code evaluation required."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
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

    def repeat(self, times: int, *, variations: Mapping[int, Pattern] | None = None) -> Pattern:
        """Repeat a phrase, optionally replacing selected zero-based repetitions.

        Replacements must have exactly the same length, so fills cannot move later bars.
        """
        if isinstance(times, bool) or not isinstance(times, int) or times < 1:
            raise ValueError("times must be a positive integer")
        if variations is None:
            variations = {}
        if not isinstance(variations, Mapping):
            raise ValueError("variations must map repetition indices to Patterns")
        for index, phrase in variations.items():
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < times:
                raise ValueError("variation indices must be integers from 0 to times - 1")
            if not isinstance(phrase, Pattern) or phrase.beats != self.beats:
                raise ValueError("variations must be Patterns with the same length as the source")
        return Pattern(
            tuple(
                note
                for index in range(times)
                for note in variations.get(index, self).at(index * self.beats)
            ),
            self.beats * times,
        )

    def accent(self, weights: Sequence[float], *, step: float = 0.5) -> Pattern:
        """Multiply velocities by a repeating beat grid, including silent grid cells.

        Notes starting in the same cell share a weight, including chord tones.
        Apply before swing when accents should follow the original straight grid.
        """
        if (
            not isinstance(weights, Sequence)
            or isinstance(weights, (str, bytes, bytearray))
            or not weights
        ):
            raise ValueError("weights must be a nonempty sequence of positive finite numbers")
        _positive(step, "step")
        for weight in weights:
            _positive(weight, "weight")

        def weight_at(beat: float) -> float:
            cell = beat / step
            if not math.isfinite(cell):
                raise ValueError("accent grid position must be finite")
            # Keep mathematically exact boundaries stable under decimal beat arithmetic.
            nearest = round(cell)
            if math.isclose(cell, nearest, abs_tol=4 * math.ulp(cell), rel_tol=0):
                cell = nearest
            return weights[math.floor(cell) % len(weights)]

        return Pattern(
            tuple(
                Note(**{**note.model_dump(), "velocity": note.velocity * weight_at(note.start)})
                for note in self.notes
            ),
            self.beats,
        )

    @classmethod
    def euclidean(
        cls,
        pulses: int,
        steps: int,
        *,
        pitch: int | str = 60,
        step: float = 0.5,
        rotation: int = 0,
        gate: float = 0.8,
        velocity: float = 0.8,
    ) -> Pattern:
        """Spread pulses across a step grid; positive rotation delays hits cyclically.

        The unrotated grid starts with a hit when pulses > 0. Zero pulses creates
        silence with the full grid length. All parameters are validated for silence.
        """
        for value, name in ((pulses, "pulses"), (steps, "steps"), (rotation, "rotation")):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        if steps < 1 or not 0 <= pulses <= steps:
            raise ValueError("steps must be positive and pulses must be between 0 and steps")
        midi_pitch(pitch)
        return cls.sequence(
            [
                pitch if ((index - rotation) * pulses) % steps < pulses else None
                for index in range(steps)
            ],
            step=step,
            gate=gate,
            velocity=velocity,
        )

    def reverse(self) -> Pattern:
        """Mirror note intervals within the phrase, including leading/trailing rests.

        This reverses the score, not the waveform. Durations and controls stay intact.
        Returned notes are ordered by onset, with simultaneous notes kept stable.
        """
        notes = (
            Note(
                **{**note.model_dump(), "start": max(0, self.beats - (note.start + note.duration))}
            )
            for note in self.notes
        )
        return Pattern(tuple(sorted(notes, key=lambda note: note.start)), self.beats)

    def swing(self, ratio: float = 2 / 3, *, step: float = 0.5) -> Pattern:
        """Warp each pair of steps to a long/short division without changing length.

        Ratio 0.5 is straight; 2/3 gives a triplet feel. Both note starts and ends
        follow the warp, preserving connected notes. Release seconds are unchanged.
        Phrase length must contain complete pairs; ratio must be strictly inside (0, 1).
        """
        _positive(ratio, "ratio")
        _positive(step, "step")
        if ratio >= 1:
            raise ValueError("ratio must be less than 1")
        pair = 2 * step
        _positive(pair, "step pair")
        pairs = self.beats / pair
        if (
            not math.isfinite(pairs)
            or not math.isclose(pairs, round(pairs), abs_tol=4 * math.ulp(pairs), rel_tol=0)
            or pairs < 1
        ):
            raise ValueError("swing requires a phrase containing complete pairs of steps")
        if ratio == 0.5:
            return self

        def warp(beat: float) -> float:
            cycle, within = divmod(beat, pair)
            if within <= step:
                return cycle * pair + within * 2 * ratio
            return cycle * pair + pair * ratio + (within - step) * 2 * (1 - ratio)

        return Pattern(
            tuple(
                Note(
                    **{
                        **note.model_dump(),
                        "start": warp(note.start),
                        "duration": warp(note.start + note.duration) - warp(note.start),
                    }
                )
                for note in self.notes
            ),
            self.beats,
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
