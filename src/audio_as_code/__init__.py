"""Compose, validate, render, and inspect music as code."""

from .inspection import inspect_score
from .instruments import get_instrument, instrument_catalog, list_instruments
from .midi import export_midi
from .model import (
    Automation,
    AutomationPoint,
    Delay,
    Note,
    PedalEvent,
    Reverb,
    Song,
    TempoChange,
    Tone,
    Track,
    midi_pitch,
)
from .pattern import Pattern
from .render import analyze_wav, render, render_audio

__version__ = "0.1.0"
__all__ = [
    "Automation",
    "AutomationPoint",
    "Delay",
    "Note",
    "Pattern",
    "PedalEvent",
    "Reverb",
    "Song",
    "TempoChange",
    "Tone",
    "Track",
    "analyze_wav",
    "export_midi",
    "get_instrument",
    "inspect_score",
    "instrument_catalog",
    "list_instruments",
    "midi_pitch",
    "render",
    "render_audio",
]
