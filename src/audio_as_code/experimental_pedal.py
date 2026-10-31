"""Non-serialized piano depth experiment; not a version 1 score control."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ._audio import _metrics
from ._voices import _voice
from .model import Song, midi_pitch
from .render import RenderResult, _note_seed


@dataclass(frozen=True)
class PedalDepth:
    """Step depth: 0 is lifted, 1 is held. Intermediate states add damping."""

    beat: float
    depth: float

    def __post_init__(self) -> None:
        for name, value in (("beat", self.beat), ("depth", self.depth)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite nonnegative number")
        if self.depth > 1:
            raise ValueError("depth must be in 0..1")


def render_pedal_depth(song: Song, events: tuple[PedalDepth, ...]) -> RenderResult:
    """Render a bounded, one-track piano damping experiment from a sidecar.

    Key-held voices are unaffected. After key release, the envelope accumulates
    damping at 60*(1-depth)**2 nepers/second. Later pedal presses never restore
    lost energy. Natural string decay remains part of the generated voice.
    """
    song = Song.model_validate(song.model_dump())
    events = tuple(events)
    if len(events) > 1024 or any(not isinstance(e, PedalDepth) for e in events):
        raise ValueError("events must contain at most 1024 PedalDepth values")
    if any(a.beat >= b.beat for a, b in zip(events, events[1:], strict=False)):
        raise ValueError("depth events must have strictly increasing beats")
    if any(e.beat > song.beats for e in events):
        raise ValueError("depth event exceeds song end")
    if len(song.tracks) != 1 or song.tracks[0].instrument != "piano":
        raise ValueError("experiment requires exactly one piano track")
    track = song.tracks[0]
    if (
        song.effects
        or song.automation
        or song.mastering
        or track.effects
        or track.automation
        or track.pedal
        or track.release_seconds
        or any(n.release_seconds is not None for n in track.notes)
    ):
        raise ValueError(
            "experiment requires dry piano without pedal, release or automation controls"
        )
    rate = song.sample_rate
    musical_frames = round(song.seconds * rate)
    frames = musical_frames + round(0.25 * rate)
    if frames > 300 * rate:
        raise ValueError("depth experiment including damper tail exceeds 300 seconds")
    # Bound dense scores as well as wall-clock duration before allocating audio.
    # Voices are synthesized independently through song end, one at a time.
    if len(track.notes) > 4096:
        raise ValueError("depth experiment exceeds 4096 notes")
    scheduled = [
        (
            round(song.beat_to_seconds(note.start) * rate),
            round(song.beat_to_seconds(note.start + note.duration) * rate),
        )
        for note in track.notes
    ]
    voice_frames = sum(frames - start for start, off in scheduled if off > start)
    if voice_frames > 20_000_000:
        raise ValueError("depth experiment exceeds 20000000 synthesized voice frames")
    depth = np.zeros(frames, dtype=np.float64)
    for index, event in enumerate(events):
        start = round(song.beat_to_seconds(event.beat) * rate)
        end = (
            round(song.beat_to_seconds(events[index + 1].beat) * rate)
            if index + 1 < len(events)
            else musical_frames
        )
        depth[start:end] = event.depth
    damping = 60 * (1 - depth) ** 2 / rate
    integral = np.concatenate(([0.0], np.cumsum(damping)))
    mono = np.zeros(frames, dtype=np.float32)
    for index, note in enumerate(track.notes):
        start, off = scheduled[index]
        if off <= start:
            continue
        voice = _voice(
            "piano",
            midi_pitch(note.pitch),
            frames - start,
            rate,
            _note_seed(song.seed, track.name, index),
            note.velocity,
            track.tone,
            held_frames=musical_frames - start,
        )
        envelope = np.ones(frames - start, dtype=np.float64)
        envelope[off - start :] = np.exp(-(integral[off:frames] - integral[off]))
        # Explicit finite horizon, independent of score length or depth.
        fade = min(frames - off, round(0.01 * rate))
        if fade:
            envelope[-fade:] *= np.linspace(1, 0, fade)
        mono[start:] += voice * envelope * note.velocity
    angle = (track.pan + 1) * np.pi / 4
    audio = np.column_stack((mono * np.cos(angle), mono * np.sin(angle)))
    audio *= track.gain * song.master_gain
    peak = float(np.max(np.abs(audio)))
    gain = min(1.0, 0.95 / peak) if peak else 1.0
    audio *= gain
    return RenderResult(
        audio.astype(np.float32),
        {
            "audio": _metrics(audio, rate),
            "experimental": True,
            "gain_applied": gain,
            "depth_range": [0, 1],
            "finite": bool(np.all(np.isfinite(audio))),
            "musical_frames": musical_frames,
            "synthesized_voice_frames": voice_frames,
            "damper_tail_seconds": 0.25,
            "events": [{"beat": e.beat, "depth": e.depth} for e in events],
            "midi_cc64_proposal": [
                {"tick": round(e.beat * 480), "value": round(e.depth * 127)} for e in events
            ]
            + [{"tick": round(song.beats * 480), "value": 0}],
            "warnings": [
                "Experimental sidecar only; version 1 score JSON still accepts binary pedal only.",
                "Standard export_midi does not export this sidecar. "
                "CC64 values above are a proposal; "
                "many receivers threshold CC64 and cannot reproduce depth or this WAV.",
                "No sympathetic resonance, pedal noise, shared strings or perceptual validation.",
            ],
        },
    )
