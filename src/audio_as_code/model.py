"""Versioned, portable musical data. All time values are quarter-note beats."""

from __future__ import annotations

import math
import re
from bisect import bisect_right
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from .instruments import KIT_NOTES, Instrument, get_instrument, require_instrument

Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]
MidiPitch = Annotated[StrictInt, Field(ge=0, le=127)]
NoteName = Annotated[str, Field(strict=True, pattern=r"^[A-Ga-g](?:#|b)?-?[0-9]$")]
Pitch = MidiPitch | NoteName
Articulation = Literal["soft", "accented", "slap", "pop", "muted"]


def midi_pitch(value: int | str) -> int:
    """Convert scientific pitch notation (C4 = 60, A4 = 69) to MIDI."""
    if isinstance(value, bool):
        raise ValueError("pitch must be a MIDI integer or a note name, not a boolean")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        match = re.fullmatch(r"([A-Ga-g])([#b]?)(-?[0-9])", value)
        if not match:
            raise ValueError(f"invalid pitch {value!r}; use a name such as C4, F#3, or Bb2")
        letter, accidental, octave = match.groups()
        pitch_class = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        result = (int(octave) + 1) * 12 + pitch_class[letter.upper()]
        result += {"": 0, "#": 1, "b": -1}[accidental]
    else:
        raise ValueError("pitch must be a MIDI integer or a note name")
    if not 0 <= result <= 127:
        raise ValueError(f"pitch {value!r} falls outside MIDI range 0..127")
    return result


class ScoreModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class TempoChange(ScoreModel):
    beat: Annotated[Number, Field(ge=0)]
    bpm: Annotated[Number, Field(ge=20, le=300)]


class PedalEvent(ScoreModel):
    """Binary piano damper pedal; events apply before note-offs at the same beat."""

    beat: Annotated[Number, Field(ge=0)]
    down: StrictBool


class AutomationPoint(ScoreModel):
    beat: Annotated[Number, Field(ge=0)]
    value: Annotated[Number, Field(ge=-1, le=1)]


class Automation(ScoreModel):
    parameter: Literal["gain", "pan", "master_gain"]
    points: Annotated[tuple[AutomationPoint, ...], Field(min_length=1, max_length=1024)]
    interpolation: Literal["linear", "step"] = "linear"

    @model_validator(mode="after")
    def validate_points(self) -> Automation:
        if any(a.beat >= b.beat for a, b in zip(self.points, self.points[1:], strict=False)):
            raise ValueError("automation points must have strictly increasing beats")
        if self.parameter != "pan" and any(point.value < 0 for point in self.points):
            raise ValueError("gain automation values must be between 0 and 1")
        return self


class Delay(ScoreModel):
    """Finite echo train: first echo at full wet gain, successive echoes decay."""

    type: Literal["delay"] = "delay"
    time_seconds: Annotated[Number, Field(ge=0.01, le=2)] = 0.25
    feedback: Annotated[Number, Field(ge=0, le=0.85)] = 0.4
    repeats: Annotated[StrictInt, Field(ge=1, le=16)] = 4
    mix: Annotated[Number, Field(ge=0, le=1)] = 0.2


class Reverb(ScoreModel):
    """Generated stereo comb network with diffusion; no measured impulse response."""

    type: Literal["reverb"] = "reverb"
    decay_seconds: Annotated[Number, Field(ge=0.1, le=5)] = 1.2
    mix: Annotated[Number, Field(ge=0, le=1)] = 0.2


class Filter(ScoreModel):
    """Resonant state-variable filter with an optional whole-track frequency sweep."""

    type: Literal["filter"] = "filter"
    mode: Literal["lowpass", "highpass", "bandpass"] = "lowpass"
    cutoff_hz: Annotated[Number, Field(ge=30, le=20000)] = 2000
    resonance: Annotated[Number, Field(ge=0, le=1)] = 0.2
    end_cutoff_hz: Annotated[Number, Field(ge=30, le=20000)] | None = None
    sweep_seconds: Annotated[Number, Field(ge=0.01, le=300)] = 1
    mix: Annotated[Number, Field(ge=0, le=1)] = 1


class Distortion(ScoreModel):
    """Symmetric tanh saturation with four-times oversampling."""

    type: Literal["distortion"] = "distortion"
    drive: Annotated[Number, Field(ge=1, le=20)] = 2
    mix: Annotated[Number, Field(ge=0, le=1)] = 0.5


class Chorus(ScoreModel):
    """Stereo modulated fractional delay; no feedback or recorded response."""

    type: Literal["chorus"] = "chorus"
    rate_hz: Annotated[Number, Field(ge=0.05, le=8)] = 0.7
    depth_ms: Annotated[Number, Field(ge=0, le=10)] = 3
    delay_ms: Annotated[Number, Field(ge=11, le=40)] = 18
    mix: Annotated[Number, Field(ge=0, le=1)] = 0.35


class Phaser(ScoreModel):
    """Four moving first-order all-pass stages, without feedback."""

    type: Literal["phaser"] = "phaser"
    rate_hz: Annotated[Number, Field(ge=0.05, le=8)] = 0.4
    depth: Annotated[Number, Field(ge=0, le=1)] = 0.7
    mix: Annotated[Number, Field(ge=0, le=1)] = 0.5


class Tremolo(ScoreModel):
    """Tempo-synced gain modulation; period is measured in quarter-note beats."""

    type: Literal["tremolo"] = "tremolo"
    period_beats: Annotated[Number, Field(ge=0.125, le=32)] = 0.5
    depth: Annotated[Number, Field(ge=0, le=1)] = 0.7
    shape: Literal["sine", "gate"] = "sine"
    mix: Annotated[Number, Field(ge=0, le=1)] = 1


class Ducker(ScoreModel):
    """Beat-triggered gain dips; a scheduled envelope, not an audio sidechain compressor."""

    type: Literal["ducker"] = "ducker"
    trigger_beats: Annotated[tuple[Annotated[Number, Field(ge=0)], ...], Field(max_length=4096)]
    depth: Annotated[Number, Field(ge=0, le=1)] = 0.75
    attack_seconds: Annotated[Number, Field(ge=0.001, le=0.1)] = 0.005
    release_seconds: Annotated[Number, Field(ge=0.01, le=2)] = 0.18
    mix: Annotated[Number, Field(ge=0, le=1)] = 1

    @model_validator(mode="after")
    def ordered_triggers(self) -> Ducker:
        if any(a >= b for a, b in zip(self.trigger_beats, self.trigger_beats[1:], strict=False)):
            raise ValueError("ducker trigger_beats must be strictly increasing")
        return self


Effect = Annotated[
    Delay | Reverb | Filter | Distortion | Chorus | Phaser | Tremolo | Ducker,
    Field(discriminator="type"),
]


def _validate_lanes(lanes: tuple[Automation, ...], allowed: set[str]) -> None:
    names = [lane.parameter for lane in lanes]
    if len(names) != len(set(names)) or not set(names) <= allowed:
        raise ValueError(f"automation parameters must be unique and drawn from {sorted(allowed)}")


class Note(ScoreModel):
    pitch: Pitch = "C4"
    start: Annotated[Number, Field(ge=0)] = 0
    duration: Annotated[Number, Field(gt=0)] = 1
    velocity: Annotated[Number, Field(gt=0, le=1)] = 0.8
    release_seconds: Annotated[Number, Field(ge=0, le=10)] | None = None
    articulation: Articulation | None = None

    @field_validator("pitch")
    @classmethod
    def valid_pitch(cls, value: int | str) -> int | str:
        midi_pitch(value)
        return value


class Tone(ScoreModel):
    """Instrument-specific generated tone controls; never refers to an audio asset."""

    brightness: Annotated[Number, Field(ge=0, le=1)] = 0.5
    decay_seconds: Annotated[Number, Field(ge=0.1, le=20)] | None = None
    pluck_position: Annotated[Number, Field(ge=0.05, le=0.45)] | None = None
    breath: Annotated[Number, Field(ge=0, le=1)] | None = None
    vibrato_depth_cents: Annotated[Number, Field(ge=0, le=100)] | None = None
    vibrato_rate_hz: Annotated[Number, Field(ge=0.1, le=12)] | None = None
    glide_semitones: Annotated[Number, Field(ge=-24, le=24)] | None = None
    detune_cents: Annotated[Number, Field(ge=0, le=40)] | None = None
    cutoff_hz: Annotated[Number, Field(ge=20, le=20000)] | None = None
    resonance: Annotated[Number, Field(ge=0, le=1)] | None = None
    filter_decay_seconds: Annotated[Number, Field(ge=0.01, le=10)] | None = None
    filter_env_octaves: Annotated[Number, Field(ge=0, le=6)] | None = None
    glide_seconds: Annotated[Number, Field(ge=0.005, le=2)] | None = None
    fm_index: Annotated[Number, Field(ge=0, le=12)] | None = None
    fm_ratio: Annotated[Number, Field(ge=0.25, le=8)] | None = None
    modulation_rate_hz: Annotated[Number, Field(ge=0.05, le=20)] | None = None
    tuning_semitones: Annotated[Number, Field(ge=-24, le=24)] | None = None


class Track(ScoreModel):
    name: Annotated[str, Field(strict=True, min_length=1, max_length=80)]
    instrument: Instrument = "pluck"
    gain: Annotated[Number, Field(ge=0, le=1)] = 0.6
    pan: Annotated[Number, Field(ge=-1, le=1)] = 0
    tone: Tone | None = None
    notes: tuple[Note, ...] = ()
    release_seconds: Annotated[Number, Field(ge=0, le=10)] = 0
    articulation: Articulation | None = None
    automation: Annotated[tuple[Automation, ...], Field(max_length=2)] = ()
    effects: Annotated[tuple[Effect, ...], Field(max_length=4)] = ()

    pedal: Annotated[tuple[PedalEvent, ...], Field(max_length=1024)] = ()

    @field_validator("instrument", mode="before")
    @classmethod
    def available_instrument(cls, value: object) -> object:
        if isinstance(value, str):
            require_instrument(value)
        return value

    @model_validator(mode="after")
    def validate_tone(self) -> Track:
        _validate_lanes(self.automation, {"gain", "pan"})
        articulations = get_instrument(self.instrument).articulations
        if self.articulation is not None and self.articulation not in articulations:
            raise ValueError(
                f"articulation {self.articulation!r} is not supported by {self.instrument}"
            )
        for index, note in enumerate(self.notes):
            if note.articulation is not None and note.articulation not in articulations:
                raise ValueError(
                    f"note {index}: articulation {note.articulation!r} "
                    f"is not supported by {self.instrument}"
                )
        if self.pedal:
            if self.instrument != "piano":
                raise ValueError("pedal events are supported only by piano")
            if any(a.beat >= b.beat for a, b in zip(self.pedal, self.pedal[1:], strict=False)):
                raise ValueError("pedal events must have strictly increasing beats")
            if any(event.down != (index % 2 == 0) for index, event in enumerate(self.pedal)):
                raise ValueError("pedal events must alternate down/up, starting with down")
        if self.instrument == "drum_machine":
            for note in self.notes:
                if midi_pitch(note.pitch) not in KIT_NOTES:
                    raise ValueError(f"drum_machine pitch must be one of {sorted(KIT_NOTES)}")
        if self.tone is not None:
            supported = get_instrument(self.instrument).tone_controls
            if not supported:
                raise ValueError(f"tone controls are not supported by {self.instrument}")
            for name, value in self.tone.model_dump().items():
                if value is not None and name not in supported:
                    raise ValueError(f"{name} is not supported by {self.instrument}")
        return self

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("track name must contain a visible character")
        return value


class Song(ScoreModel):
    schema_version: Literal["1"] = "1"
    title: Annotated[str, Field(strict=True, min_length=1, max_length=200)] = "Untitled"
    bpm: Annotated[Number, Field(ge=20, le=300)] = 120
    beats: Annotated[Number, Field(gt=0, le=65536)] = 16
    sample_rate: Literal[22050, 44100, 48000] = 44100
    seed: Annotated[StrictInt, Field(ge=0, le=4294967295)] = 0
    master_gain: Annotated[Number, Field(ge=0, le=1)] = 0.8
    tracks: Annotated[tuple[Track, ...], Field(min_length=1, max_length=64)]
    tempo_map: Annotated[tuple[TempoChange, ...], Field(max_length=1024)] = ()
    automation: Annotated[tuple[Automation, ...], Field(max_length=1)] = ()
    effects: Annotated[tuple[Effect, ...], Field(max_length=4)] = ()

    @model_validator(mode="after")
    def validate_arrangement(self) -> Song:
        _validate_lanes(self.automation, {"master_gain"})
        if any(a.beat >= b.beat for a, b in zip(self.tempo_map, self.tempo_map[1:], strict=False)):
            raise ValueError("tempo_map must have strictly increasing beats")
        if any(change.beat >= self.beats for change in self.tempo_map):
            raise ValueError("tempo changes must occur before the song ends")
        for owner in (self, *self.tracks):
            for effect in owner.effects:
                if isinstance(effect, Ducker) and any(
                    b >= self.beats for b in effect.trigger_beats
                ):
                    raise ValueError("ducker trigger_beats must occur before the song ends")
            for lane in owner.automation:
                if lane.points[-1].beat > self.beats:
                    raise ValueError("automation points must not exceed the song's beats")
        names: set[str] = set()
        count = 0
        for track in self.tracks:
            if track.pedal and track.pedal[-1].beat > self.beats:
                raise ValueError("pedal events must not exceed the song's beats")
            if track.name in names:
                raise ValueError(f"duplicate track name: {track.name!r}")
            names.add(track.name)
            count += len(track.notes)
            for index, note in enumerate(track.notes):
                end = note.start + note.duration
                if not math.isfinite(end) or end > self.beats + 1e-9:
                    raise ValueError(
                        f"track {track.name!r}, note {index}: ends at beat {end}; "
                        f"song ends at {self.beats}"
                    )
        if count > 100000:
            raise ValueError("a score may contain at most 100000 notes")
        return self

    @property
    def seconds(self) -> float:
        return self.beat_to_seconds(self.beats)

    def beat_to_seconds(self, beat: float) -> float:
        """Integrate piecewise-constant BPM; the last tempo continues beyond the score."""
        if not math.isfinite(beat) or beat < 0:
            raise ValueError("beat must be finite and nonnegative")
        if not self.tempo_map:
            return beat * 60 / self.bpm
        seconds, previous, bpm = 0.0, 0.0, self.bpm
        for change in self.tempo_map:
            if change.beat > beat:
                break
            seconds += (change.beat - previous) * 60 / bpm
            previous, bpm = change.beat, change.bpm
        return seconds + (beat - previous) * 60 / bpm

    @property
    def render_seconds(self) -> float:
        from .effects import effects_tail

        end = self.seconds
        for track in self.tracks:
            dry_end = max(
                (
                    self.beat_to_seconds(self.note_gate_end(track, n))
                    + self.note_release_seconds(track, n)
                    for n in track.notes
                ),
                default=0.0,
            )
            end = max(end, dry_end + effects_tail(track.effects))
        return end + effects_tail(self.effects)

    def note_gate_end(self, track: Track, note: Note) -> float:
        """Written key release, extended to pedal lift when caught by the damper pedal."""
        end = note.start + note.duration
        index = bisect_right(track.pedal, end, key=lambda event: event.beat)
        if index and track.pedal[index - 1].down:
            return track.pedal[index].beat if index < len(track.pedal) else max(end, self.beats)
        return end

    def note_release_seconds(self, track: Track, note: Note) -> float:
        """A caught piano note defaults to a 120ms damper tail after pedal lift."""
        if note.release_seconds is not None:
            return note.release_seconds
        if track.release_seconds:
            return track.release_seconds
        return 0.12 if self.note_gate_end(track, note) > note.start + note.duration else 0.0

    @classmethod
    def load(cls, path: str | Path) -> Song:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8-sig"))

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
