"""Compose, validate, render, and inspect music as code."""

from .arrangement import (
    Arrangement,
    LoopRegion,
    Section,
    beat_at_seconds,
    place_at_seconds,
    render_loop_preview,
)
from .inspection import inspect_score
from .instruments import get_instrument, instrument_catalog, list_instruments
from .loudness import measure_loudness
from .midi import export_midi
from .mixing import MixEdit, MixResult, apply_mix, audition_song, inspect_mix
from .model import (
    Automation,
    AutomationPoint,
    Chorus,
    Delay,
    Distortion,
    Ducker,
    Filter,
    Note,
    PedalEvent,
    Phaser,
    Reverb,
    Song,
    TempoChange,
    Tone,
    Track,
    Tremolo,
    midi_pitch,
)
from .pattern import Pattern
from .project_setup import doctor, init_project
from .render import (
    RenderCancelled,
    RenderProgress,
    analyze_wav,
    render,
    render_audio,
    render_preview,
    render_preview_audio,
)

__version__ = "0.4.0"
__all__ = [
    "Arrangement",
    "Automation",
    "AutomationPoint",
    "Chorus",
    "Delay",
    "Distortion",
    "Ducker",
    "Filter",
    "LoopRegion",
    "MixEdit",
    "MixResult",
    "Note",
    "Pattern",
    "PedalEvent",
    "Phaser",
    "Reverb",
    "RenderCancelled",
    "RenderProgress",
    "Section",
    "Song",
    "TempoChange",
    "Tone",
    "Track",
    "Tremolo",
    "analyze_wav",
    "apply_mix",
    "audition_song",
    "beat_at_seconds",
    "doctor",
    "export_midi",
    "get_instrument",
    "inspect_score",
    "inspect_mix",
    "init_project",
    "instrument_catalog",
    "list_instruments",
    "measure_loudness",
    "midi_pitch",
    "place_at_seconds",
    "render",
    "render_audio",
    "render_loop_preview",
    "render_preview",
    "render_preview_audio",
]
