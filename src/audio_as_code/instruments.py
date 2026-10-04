"""Instrument families and the code-generated synthesis engines behind them.

Planned entries describe the framework's scope; only available entries may appear
in scores. The metadata also supplies tone capabilities and MIDI mappings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Literal

Instrument = Literal[
    "sine",
    "triangle",
    "pluck",
    "bass",
    "pad",
    "kick",
    "snare",
    "hat",
    "guitar",
    "marimba",
    "bell",
    "electric_guitar",
    "bass_guitar",
    "harp",
    "ukulele",
    "banjo",
    "violin",
    "viola",
    "cello",
    "double_bass",
    "piano",
    "electric_piano",
    "organ",
    "harpsichord",
    "flute",
    "clarinet",
    "saxophone",
    "oboe",
    "bassoon",
    "trumpet",
    "trombone",
    "french_horn",
    "tuba",
    "toms",
    "cymbal",
    "congas",
    "bongos",
    "tambourine",
    "xylophone",
    "vibraphone",
    "glockenspiel",
    "timpani",
    "synthesizer",
    "drum_machine",
    "theremin",
    "mandolin",
    "kalimba",
    "celesta",
    "recorder",
]
Status = Literal["available", "planned"]
FamilyId = Literal[
    "plucked_strings",
    "bowed_strings",
    "keyboards",
    "woodwinds",
    "brass",
    "percussion",
    "pitched_percussion",
    "electronic",
]
EngineId = Literal["string", "air_column", "modal", "membrane", "electronic"]


@dataclass(frozen=True)
class Family:
    id: FamilyId
    name: str


@dataclass(frozen=True)
class Engine:
    id: EngineId
    name: str
    status: Status
    description: str


@dataclass(frozen=True)
class InstrumentInfo:
    id: str
    name: str
    family: FamilyId
    engine: EngineId
    status: Status
    description: str
    tone_controls: tuple[str, ...] = ()
    default_decay_seconds: float | None = None
    midi_program: int | None = None
    midi_note: int | None = None
    preview_pitch: int = 60
    default_tone: tuple[tuple[str, float], ...] = ()
    articulations: tuple[str, ...] = ()


FAMILIES = (
    Family("plucked_strings", "Plucked strings"),
    Family("bowed_strings", "Bowed strings"),
    Family("keyboards", "Keyboards"),
    Family("woodwinds", "Woodwinds"),
    Family("brass", "Brass"),
    Family("percussion", "Drums and percussion"),
    Family("pitched_percussion", "Pitched percussion"),
    Family("electronic", "Electronic"),
)

ENGINES = (
    Engine(
        "string",
        "Vibrating strings",
        "available",
        "Damped guitar delay loop, modal plucked/struck strings, and spectral "
        "bowed-tone prototypes.",
    ),
    Engine(
        "air_column",
        "Air columns",
        "available",
        "Harmonic source/filter approximations of pipes, reeds, and brass; no "
        "nonlinear bore solver yet.",
    ),
    Engine(
        "modal",
        "Bars, bells, and plates",
        "available",
        "Damped modes for bars, bells, tines, and plate-inspired metal resonances.",
    ),
    Engine(
        "membrane",
        "Membranes",
        "available",
        "Modal drumhead approximations with strike noise and tension relaxation; no "
        "coupled cavity solver.",
    ),
    Engine(
        "electronic",
        "Electronic synthesis",
        "available",
        "Oscillators, harmonic sums, noise, envelopes, and generated percussion.",
    ),
)

_DECAY_CONTROLS = ("brightness", "decay_seconds")

INSTRUMENTS = (
    InstrumentInfo(
        "guitar",
        "Acoustic guitar",
        "plucked_strings",
        "string",
        "available",
        "Tuned plucked-string loop with generated contact noise and a driven body "
        "resonance approximation; no coupled body solver.",
        (*_DECAY_CONTROLS, "pluck_position"),
        3.0,
        midi_program=24,
    ),
    InstrumentInfo(
        "electric_guitar",
        "Electric guitar",
        "plucked_strings",
        "string",
        "available",
        "Modal steel-string pluck with pickup-position response; clean tone, no "
        "amplifier circuit model.",
        tone_controls=("brightness", "decay_seconds", "pluck_position"),
        default_decay_seconds=4.5,
        midi_program=27,
        midi_note=None,
        preview_pitch=52,
        default_tone=(("pluck_position", 0.16),),
    ),
    InstrumentInfo(
        "bass_guitar",
        "Bass guitar",
        "plucked_strings",
        "string",
        "available",
        "Low modal strings with pickup response and strong upper-mode damping; no "
        "fret-contact model.",
        tone_controls=("brightness", "decay_seconds", "pluck_position"),
        default_decay_seconds=4.5,
        midi_program=33,
        midi_note=None,
        preview_pitch=36,
        default_tone=(("pluck_position", 0.24),),
    ),
    InstrumentInfo(
        "harp",
        "Harp",
        "plucked_strings",
        "string",
        "available",
        "Long-decay modal string with lightly detuned polarizations and driven body "
        "resonances; no sympathetic-string coupling.",
        tone_controls=("brightness", "decay_seconds", "pluck_position"),
        default_decay_seconds=6,
        midi_program=46,
        midi_note=None,
        preview_pitch=60,
        default_tone=(("pluck_position", 0.32),),
    ),
    InstrumentInfo(
        "ukulele",
        "Ukulele",
        "plucked_strings",
        "string",
        "available",
        "Short modal pluck with fast upper-mode decay and driven small-body resonances.",
        tone_controls=("brightness", "decay_seconds", "pluck_position"),
        default_decay_seconds=1.8,
        midi_program=24,
        midi_note=None,
        preview_pitch=67,
        default_tone=(("pluck_position", 0.25),),
    ),
    InstrumentInfo(
        "banjo",
        "Banjo",
        "plucked_strings",
        "string",
        "available",
        "Bright modal pluck driving a designed drumhead-like response; no "
        "coupled head/string solver.",
        tone_controls=("brightness", "decay_seconds", "pluck_position"),
        default_decay_seconds=1.6,
        midi_program=105,
        midi_note=None,
        preview_pitch=60,
        default_tone=(("pluck_position", 0.12),),
    ),
    InstrumentInfo(
        "violin",
        "Violin",
        "bowed_strings",
        "string",
        "available",
        "Bowed-tone harmonic source/filter approximation with body formants, onset, "
        "evolving bow noise, and delayed vibrato; no friction solver.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz"),
        default_decay_seconds=None,
        midi_program=40,
        midi_note=None,
        preview_pitch=69,
        default_tone=(("vibrato_depth_cents", 14), ("vibrato_rate_hz", 5.5)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "viola",
        "Viola",
        "bowed_strings",
        "string",
        "available",
        "Bowed-tone spectral approximation with lower body formants, a slower "
        "onset, bow noise, and vibrato.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz"),
        default_decay_seconds=None,
        midi_program=41,
        midi_note=None,
        preview_pitch=60,
        default_tone=(("vibrato_depth_cents", 12), ("vibrato_rate_hz", 5.1)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "cello",
        "Cello",
        "bowed_strings",
        "string",
        "available",
        "Bowed-tone spectral approximation with low body formants, gradual onset, "
        "bow noise, and vibrato.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz"),
        default_decay_seconds=None,
        midi_program=42,
        midi_note=None,
        preview_pitch=48,
        default_tone=(("vibrato_depth_cents", 13), ("vibrato_rate_hz", 4.7)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "double_bass",
        "Double bass",
        "bowed_strings",
        "string",
        "available",
        "Low bowed-tone spectral approximation with slow onset and bow noise; "
        "pizzicato is not implemented.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz"),
        default_decay_seconds=None,
        midi_program=43,
        midi_note=None,
        preview_pitch=36,
        default_tone=(("vibrato_depth_cents", 8), ("vibrato_rate_hz", 4.2)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "piano",
        "Piano",
        "keyboards",
        "string",
        "available",
        "Finite hammer-driven stiff strings with shared unison bridge losses and a designed "
        "soundboard response; binary Track.pedal damper gates, without half-pedal or "
        "sympathetic resonance.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=5,
        midi_program=0,
        midi_note=None,
        preview_pitch=60,
        default_tone=(),
    ),
    InstrumentInfo(
        "electric_piano",
        "Electric piano",
        "keyboards",
        "modal",
        "available",
        "Struck tine-like modes with a short bright attack and gentle amplitude "
        "tremolo; no pickup circuit solver.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=4,
        midi_program=4,
        midi_note=None,
        preview_pitch=60,
        default_tone=(),
    ),
    InstrumentInfo(
        "organ",
        "Organ",
        "keyboards",
        "air_column",
        "available",
        "Sustained additive pipe-registration approximation with generated onset "
        "chiff; no airflow solver.",
        tone_controls=("brightness", "breath"),
        default_decay_seconds=None,
        midi_program=19,
        midi_note=None,
        preview_pitch=60,
        default_tone=(("breath", 0.15),),
    ),
    InstrumentInfo(
        "harpsichord",
        "Harpsichord",
        "keyboards",
        "string",
        "available",
        "Bright near-bridge modal pluck with slight unison beating and driven body resonances.",
        tone_controls=("brightness", "decay_seconds", "pluck_position"),
        default_decay_seconds=3,
        midi_program=6,
        midi_note=None,
        preview_pitch=60,
        default_tone=(("pluck_position", 0.09),),
    ),
    InstrumentInfo(
        "flute",
        "Flute",
        "woodwinds",
        "air_column",
        "available",
        "Airy harmonic source/filter approximation with weak upper partials, "
        "evolving breath noise and delayed vibrato; no jet/bore solver.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=73,
        midi_note=None,
        preview_pitch=72,
        default_tone=(("breath", 0.45), ("vibrato_depth_cents", 10), ("vibrato_rate_hz", 5)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "clarinet",
        "Clarinet",
        "woodwinds",
        "air_column",
        "available",
        "Odd-harmonic reed-tone approximation with weak even partials and generated "
        "breath; no reed/bore feedback solver.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=71,
        midi_note=None,
        preview_pitch=60,
        default_tone=(("breath", 0.12), ("vibrato_depth_cents", 0), ("vibrato_rate_hz", 5)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "saxophone",
        "Saxophone",
        "woodwinds",
        "air_column",
        "available",
        "Reed-tone spectral approximation with broad harmonics, formants, generated "
        "breath, and vibrato.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=65,
        midi_note=None,
        preview_pitch=57,
        default_tone=(("breath", 0.3), ("vibrato_depth_cents", 12), ("vibrato_rate_hz", 5.2)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "oboe",
        "Oboe",
        "woodwinds",
        "air_column",
        "available",
        "Double-reed-tone spectral approximation with strong upper harmonics, a "
        "nasal formant, breath, and vibrato.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=68,
        midi_note=None,
        preview_pitch=67,
        default_tone=(("breath", 0.16), ("vibrato_depth_cents", 9), ("vibrato_rate_hz", 5.6)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "bassoon",
        "Bassoon",
        "woodwinds",
        "air_column",
        "available",
        "Low double-reed-tone spectral approximation with designed formants, "
        "breath, and gradual onset.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=70,
        midi_note=None,
        preview_pitch=48,
        default_tone=(("breath", 0.16), ("vibrato_depth_cents", 7), ("vibrato_rate_hz", 4.8)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "trumpet",
        "Trumpet",
        "brass",
        "air_column",
        "available",
        "Brass-tone spectral approximation with a brightening onset and "
        "velocity-sensitive harmonics; no lip/bore feedback solver.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=56,
        midi_note=None,
        preview_pitch=67,
        default_tone=(("breath", 0.08), ("vibrato_depth_cents", 5), ("vibrato_rate_hz", 5.3)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "trombone",
        "Trombone",
        "brass",
        "air_column",
        "available",
        "Brass-tone spectral approximation with broad low harmonics and breath; no "
        "continuous slide geometry.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=57,
        midi_note=None,
        preview_pitch=48,
        default_tone=(("breath", 0.1), ("vibrato_depth_cents", 4), ("vibrato_rate_hz", 4.8)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "french_horn",
        "French horn",
        "brass",
        "air_column",
        "available",
        "Soft brass-tone spectral approximation with rounded harmonics and a gradual onset.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=60,
        midi_note=None,
        preview_pitch=53,
        default_tone=(("breath", 0.08), ("vibrato_depth_cents", 3), ("vibrato_rate_hz", 4.8)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "tuba",
        "Tuba",
        "brass",
        "air_column",
        "available",
        "Low brass-tone spectral approximation with a slow pressure-like onset and "
        "generated breath.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "breath"),
        default_decay_seconds=None,
        midi_program=58,
        midi_note=None,
        preview_pitch=36,
        default_tone=(("breath", 0.12), ("vibrato_depth_cents", 3), ("vibrato_rate_hz", 4)),
        articulations=("soft", "accented"),
    ),
    InstrumentInfo(
        "kick",
        "Kick",
        "percussion",
        "electronic",
        "available",
        "Synthetic pitch-swept sine drum; not a drumhead physics model.",
        midi_note=36,
    ),
    InstrumentInfo(
        "snare",
        "Snare",
        "percussion",
        "electronic",
        "available",
        "Synthetic noise and tonal transient; not a drumhead physics model.",
        midi_note=38,
    ),
    InstrumentInfo(
        "hat",
        "Hi-hat",
        "percussion",
        "electronic",
        "available",
        "Synthetic filtered-noise and inharmonic-mode hi-hat; no metal-plate physics solver.",
        midi_note=42,
    ),
    InstrumentInfo(
        "toms",
        "Toms",
        "percussion",
        "membrane",
        "available",
        "Fixed-tuning modal drumhead approximation with strike noise and relaxing "
        "tension and designed shell coloration; no shell/cavity feedback coupling.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=1.1,
        midi_program=None,
        midi_note=45,
        preview_pitch=45,
        default_tone=(),
    ),
    InstrumentInfo(
        "cymbal",
        "Cymbal",
        "percussion",
        "modal",
        "available",
        "Seeded inharmonic metal-mode cloud with frequency-dependent damping; "
        "plate-inspired, not a nonlinear plate solver.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=4,
        midi_program=None,
        midi_note=49,
        preview_pitch=49,
        default_tone=(),
    ),
    InstrumentInfo(
        "congas",
        "Congas",
        "percussion",
        "membrane",
        "available",
        "Open-hand drum approximation using designed membrane modes and a generated "
        "slap transient; one articulation.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=0.9,
        midi_program=None,
        midi_note=64,
        preview_pitch=64,
        default_tone=(),
    ),
    InstrumentInfo(
        "bongos",
        "Bongos",
        "percussion",
        "membrane",
        "available",
        "High fixed-tuning membrane modes with a short generated hand-strike "
        "transient; one articulation.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=0.55,
        midi_program=None,
        midi_note=60,
        preview_pitch=60,
        default_tone=(),
    ),
    InstrumentInfo(
        "tambourine",
        "Tambourine",
        "percussion",
        "modal",
        "available",
        "Generated jingle collisions exciting inharmonic metal modes; no recorded "
        "hits or membrane component.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=0.65,
        midi_program=None,
        midi_note=54,
        preview_pitch=54,
        default_tone=(),
    ),
    InstrumentInfo(
        "marimba",
        "Marimba",
        "pitched_percussion",
        "modal",
        "available",
        "Simplified tuned wooden-bar modes with independent decay.",
        _DECAY_CONTROLS,
        1.4,
        midi_program=12,
    ),
    InstrumentInfo(
        "xylophone",
        "Xylophone",
        "pitched_percussion",
        "modal",
        "available",
        "Bright tuned wooden-bar modal approximation with rapid overtone decay and "
        "a hard generated strike.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=0.8,
        midi_program=13,
        midi_note=None,
        preview_pitch=72,
        default_tone=(),
    ),
    InstrumentInfo(
        "vibraphone",
        "Vibraphone",
        "pitched_percussion",
        "modal",
        "available",
        "Tuned metal-bar modal approximation with long decay and 5.5 Hz amplitude tremolo.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=5.5,
        midi_program=11,
        midi_note=None,
        preview_pitch=60,
        default_tone=(),
    ),
    InstrumentInfo(
        "glockenspiel",
        "Glockenspiel",
        "pitched_percussion",
        "modal",
        "available",
        "High inharmonic metal-bar modes with a short generated strike and long ringing decay.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=5,
        midi_program=9,
        midi_note=None,
        preview_pitch=84,
        default_tone=(),
    ),
    InstrumentInfo(
        "bell",
        "Bell",
        "pitched_percussion",
        "modal",
        "available",
        "Designed inharmonic chime modes; not fitted to a particular bell.",
        _DECAY_CONTROLS,
        5.0,
        midi_program=14,
    ),
    InstrumentInfo(
        "timpani",
        "Timpani",
        "pitched_percussion",
        "membrane",
        "available",
        "Pitchable quasi-harmonic membrane modes with tension relaxation and a soft "
        "strike; no kettle-cavity solver.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=2.8,
        midi_program=47,
        midi_note=None,
        preview_pitch=43,
        default_tone=(),
    ),
    InstrumentInfo(
        "sine",
        "Sine oscillator",
        "electronic",
        "electronic",
        "available",
        "A single sinusoidal oscillator.",
        midi_program=80,
    ),
    InstrumentInfo(
        "triangle",
        "Triangle oscillator",
        "electronic",
        "electronic",
        "available",
        "A finite odd-harmonic approximation of a triangle wave.",
        midi_program=80,
    ),
    InstrumentInfo(
        "pluck",
        "Synth pluck",
        "electronic",
        "electronic",
        "available",
        "Decaying harmonic synthesis; distinct from the physical guitar voice.",
        midi_program=10,
    ),
    InstrumentInfo(
        "bass",
        "Synth bass",
        "electronic",
        "electronic",
        "available",
        "A three-harmonic bass synthesizer; distinct from a bass-guitar model.",
        midi_program=38,
    ),
    InstrumentInfo(
        "pad",
        "Synth pad",
        "electronic",
        "electronic",
        "available",
        "A sustained harmonic voice with a soft attack and release.",
        midi_program=89,
    ),
    InstrumentInfo(
        "synthesizer",
        "Multi-oscillator synthesizer",
        "electronic",
        "electronic",
        "available",
        "Three band-limited detuned harmonic oscillators with a brightness-decay "
        "filter envelope; fixed topology.",
        tone_controls=("brightness", "detune_cents"),
        default_decay_seconds=None,
        midi_program=81,
        midi_note=None,
        preview_pitch=60,
        default_tone=(("detune_cents", 8),),
    ),
    InstrumentInfo(
        "drum_machine",
        "Drum machine",
        "electronic",
        "electronic",
        "available",
        "Generated percussion kit: note pitch chooses kick, snare, hat, tom, "
        "cymbal, tambourine, bongo, or conga.",
        tone_controls=(),
        default_decay_seconds=None,
        midi_program=None,
        midi_note=36,
        preview_pitch=36,
        default_tone=(),
    ),
    InstrumentInfo(
        "theremin",
        "Theremin",
        "electronic",
        "electronic",
        "available",
        "Sustained electronic tone with vibrato and an optional exponential pitch "
        "glide into each note.",
        tone_controls=("brightness", "vibrato_depth_cents", "vibrato_rate_hz", "glide_semitones"),
        default_decay_seconds=None,
        midi_program=80,
        midi_note=None,
        preview_pitch=72,
        default_tone=(
            ("vibrato_depth_cents", 22),
            ("vibrato_rate_hz", 5.7),
            ("glide_semitones", 0),
        ),
    ),
)

# Append new voices so existing discovery entries retain their relative order.
INSTRUMENTS += (
    InstrumentInfo(
        "mandolin",
        "Mandolin",
        "plucked_strings",
        "string",
        "available",
        "Paired stiff-string normal modes with a shared bridge stiffness and projected "
        "radiation losses, plus a generated body response; no full string/body solver. "
        "Detune is the total uncoupled-string separation in cents.",
        tone_controls=("brightness", "decay_seconds", "pluck_position", "detune_cents"),
        default_decay_seconds=1.8,
        midi_program=25,
        preview_pitch=67,
        default_tone=(("pluck_position", 0.18), ("detune_cents", 4)),
    ),
    InstrumentInfo(
        "kalimba",
        "Kalimba",
        "pitched_percussion",
        "modal",
        "available",
        "Fixed-free lamella modes driven by a finite thumb-contact force, with a generated "
        "wooden-box response; idealized uniform tine, no buzz attachments or tine coupling.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=2.0,
        midi_program=108,
        preview_pitch=72,
    ),
    InstrumentInfo(
        "celesta",
        "Celesta",
        "keyboards",
        "modal",
        "available",
        "Free-free metal-bar modes driven by a finite felt-hammer force and a pitch-matched "
        "generated resonator; idealized uniform bar, no keyboard mechanics or pedal model.",
        tone_controls=("brightness", "decay_seconds"),
        default_decay_seconds=3.4,
        midi_program=8,
        preview_pitch=84,
    ),
    InstrumentInfo(
        "recorder",
        "Recorder",
        "woodwinds",
        "air_column",
        "available",
        "Soprano-like recorder prototype: band-limited asymmetric jet-source harmonics, "
        "designed bore/radiation filtering, breath and onset; no nonlinear jet/bore coupling "
        "or fingering-dependent impedance model.",
        tone_controls=("brightness", "breath", "vibrato_depth_cents", "vibrato_rate_hz"),
        midi_program=74,
        preview_pitch=79,
        default_tone=(("breath", 0.08), ("vibrato_depth_cents", 0), ("vibrato_rate_hz", 5)),
    ),
)

_BY_ID = MappingProxyType({instrument.id: instrument for instrument in INSTRUMENTS})
_FAMILY_IDS = frozenset(family.id for family in FAMILIES)
_ENGINE_IDS = frozenset(engine.id for engine in ENGINES)


def get_instrument(instrument_id: str) -> InstrumentInfo:
    """Inspect an instrument, including planned entries. Does not imply playability."""
    try:
        return _BY_ID[instrument_id]
    except KeyError:
        raise ValueError(f"unknown instrument {instrument_id!r}; use 'aac instruments'") from None


def require_instrument(instrument_id: str) -> InstrumentInfo:
    """Resolve a playable instrument; never silently substitute another sound."""
    instrument = get_instrument(instrument_id)
    if instrument.status != "available":
        raise ValueError(
            f"instrument {instrument_id!r} is planned and cannot be rendered yet; "
            "use 'aac instruments' for available voices"
        )
    return instrument


def list_instruments(
    *,
    family: str | None = None,
    engine: str | None = None,
    include_planned: bool = False,
) -> tuple[InstrumentInfo, ...]:
    """Discover playable voices by default; opt in to see the full framework scope."""
    if family is not None and family not in _FAMILY_IDS:
        raise ValueError(f"unknown instrument family {family!r}")
    if engine is not None and engine not in _ENGINE_IDS:
        raise ValueError(f"unknown synthesis engine {engine!r}")
    return tuple(
        instrument
        for instrument in INSTRUMENTS
        if (include_planned or instrument.status == "available")
        and (family is None or instrument.family == family)
        and (engine is None or instrument.engine == engine)
    )


def instrument_catalog(
    *,
    family: str | None = None,
    engine: str | None = None,
    include_planned: bool = False,
) -> dict:
    """Machine-readable discovery; engine availability denotes an initial implementation."""
    selected = list_instruments(family=family, engine=engine, include_planned=include_planned)
    return {
        "catalog_version": "1",
        "synthesis_policy": "code_only",
        "families": [asdict(item) for item in FAMILIES],
        "engines": [asdict(item) for item in ENGINES],
        "instruments": [asdict(item) for item in selected],
        "counts": {
            "available": sum(item.status == "available" for item in selected),
            "planned": sum(item.status == "planned" for item in selected),
        },
    }


PHYSICAL_INSTRUMENTS = frozenset(
    item.id for item in INSTRUMENTS if item.status == "available" and item.engine != "electronic"
)
DRUM_NOTES = MappingProxyType(
    {item.id: item.midi_note for item in INSTRUMENTS if item.midi_note is not None}
)
PROGRAMS = MappingProxyType(
    {item.id: item.midi_program for item in INSTRUMENTS if item.midi_program is not None}
)

# The drum-machine track selects generated voices by GM percussion pitch.
# Other percussion IDs keep their historical fixed-pitch export behavior.
KIT_NOTES = MappingProxyType(
    {
        36: "kick",
        38: "snare",
        42: "hat",
        45: "toms",
        49: "cymbal",
        54: "tambourine",
        60: "bongos",
        64: "congas",
    }
)
