"""Hand-designed coefficients for the shared orchestra synthesis models.

Keep playable IDs and discovery metadata in instruments.py. These immutable
profiles supply the spectra, resonances and damping used by orchestra.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class StringProfile:
    position: float
    stiffness: float
    damping: float
    tilt: float
    body: tuple[tuple[float, float, float], ...]
    pickup: float | None = None
    detune: float = 0


STRINGS = MappingProxyType(
    {
        "electric_guitar": StringProfile(0.16, 0.000025, 0.13, 1.1, (), 0.18),
        "bass_guitar": StringProfile(0.24, 0.00007, 0.2, 1.3, (), 0.27),
        "harp": StringProfile(
            0.32, 0.000015, 0.09, 1.55, ((190, 0.05, 0.07), (420, 0.025, 0.04)), detune=1.5
        ),
        "ukulele": StringProfile(
            0.25, 0.000004, 0.3, 1.7, ((270, 0.07, 0.04), (590, 0.035, 0.025))
        ),
        "banjo": StringProfile(
            0.12, 0.00004, 0.27, 0.9, ((410, 0.09, 0.06), (660, 0.06, 0.035), (1080, 0.035, 0.02))
        ),
        "harpsichord": StringProfile(0.09, 0.00002, 0.12, 0.85, ((230, 0.025, 0.025),), detune=2.5),
    }
)


@dataclass(frozen=True)
class HeldProfile:
    partials: tuple[float, ...]
    attack: float
    formants: tuple[tuple[float, float, float], ...]
    noise_band: tuple[float, float]
    bow_noise: float = 0


# Formants are center Hz, bandwidth Hz, and gain. These are designed spectra,
# not fitted body responses. Instruments retain different spectra and onsets.
HELD = MappingProxyType(
    {
        "violin": HeldProfile(
            (1, 0.7, 0.55, 0.42, 0.3, 0.26, 0.2, 0.16, 0.13, 0.1, 0.08, 0.06),
            0.065,
            ((470, 230, 0.6), (2800, 900, 1.5)),
            (900, 6500),
            0.025,
        ),
        "viola": HeldProfile(
            (1, 0.75, 0.45, 0.34, 0.3, 0.18, 0.15, 0.1, 0.08),
            0.085,
            ((320, 170, 0.75), (2200, 700, 1.2)),
            (600, 5000),
            0.022,
        ),
        "cello": HeldProfile(
            (1, 0.85, 0.45, 0.28, 0.25, 0.16, 0.12, 0.09, 0.07),
            0.105,
            ((180, 100, 0.8), (900, 380, 0.7), (1800, 700, 0.65)),
            (400, 4200),
            0.025,
        ),
        "double_bass": HeldProfile(
            (1, 0.65, 0.35, 0.3, 0.18, 0.12, 0.1, 0.07),
            0.14,
            ((95, 65, 0.75), (600, 300, 0.8)),
            (220, 2700),
            0.035,
        ),
        "flute": HeldProfile(
            (1, 0.17, 0.07, 0.03, 0.012), 0.07, ((1500, 1200, 0.12),), (900, 6500)
        ),
        "clarinet": HeldProfile(
            (1, 0.055, 0.65, 0.045, 0.35, 0.035, 0.17, 0.025, 0.08, 0.01, 0.03),
            0.035,
            ((1400, 900, 0.25),),
            (1400, 6500),
        ),
        "saxophone": HeldProfile(
            (1, 0.85, 0.58, 0.42, 0.29, 0.2, 0.14, 0.1, 0.07, 0.04),
            0.045,
            ((900, 600, 0.8), (2600, 900, 0.4)),
            (800, 5500),
        ),
        "oboe": HeldProfile(
            (1, 1.1, 0.95, 0.8, 0.6, 0.38, 0.25, 0.18, 0.1, 0.07),
            0.045,
            ((1500, 650, 1.3),),
            (1700, 7000),
        ),
        "bassoon": HeldProfile(
            (1, 0.9, 0.7, 0.45, 0.28, 0.19, 0.13, 0.08),
            0.065,
            ((500, 300, 1.2), (1500, 650, 0.3)),
            (700, 4200),
        ),
        "trumpet": HeldProfile(
            (1, 0.85, 0.8, 0.72, 0.55, 0.4, 0.28, 0.19, 0.12, 0.08, 0.04, 0.02),
            0.035,
            ((1800, 1200, 0.55),),
            (900, 5500),
        ),
        "trombone": HeldProfile(
            (1, 0.85, 0.67, 0.48, 0.35, 0.25, 0.17, 0.1, 0.07),
            0.055,
            ((800, 650, 0.6),),
            (500, 4000),
        ),
        "french_horn": HeldProfile(
            (1, 0.6, 0.28, 0.14, 0.08, 0.04, 0.025), 0.085, ((650, 450, 0.3),), (400, 3200)
        ),
        "tuba": HeldProfile(
            (1, 0.7, 0.42, 0.23, 0.13, 0.07, 0.04), 0.115, ((330, 280, 0.6),), (250, 2500)
        ),
        "organ": HeldProfile(
            (1, 0.55, 0.18, 0.32, 0.04, 0.08, 0.02, 0.12), 0.022, (), (1200, 6000)
        ),
        "theremin": HeldProfile((1, 0.16, 0.045, 0.012), 0.08, (), (1000, 3000)),
    }
)


@dataclass(frozen=True)
class ReleaseProfile:
    """Designed source loss after note-off, in seconds; not measured body decay."""

    fundamental: float
    upper_loss: float
    noise: float


# Used only by the opt-in source articulations. Upper harmonics lose energy
# faster than the fundamental; turbulent/bow noise has its own cessation time.
HELD_RELEASE = MappingProxyType(
    {
        "violin": ReleaseProfile(0.065, 0.22, 0.012),
        "viola": ReleaseProfile(0.080, 0.22, 0.015),
        "cello": ReleaseProfile(0.100, 0.24, 0.018),
        "double_bass": ReleaseProfile(0.130, 0.26, 0.022),
        "flute": ReleaseProfile(0.055, 0.32, 0.032),
        "clarinet": ReleaseProfile(0.040, 0.24, 0.018),
        "saxophone": ReleaseProfile(0.055, 0.28, 0.023),
        "oboe": ReleaseProfile(0.045, 0.25, 0.018),
        "bassoon": ReleaseProfile(0.065, 0.28, 0.025),
        "trumpet": ReleaseProfile(0.045, 0.38, 0.016),
        "trombone": ReleaseProfile(0.060, 0.36, 0.022),
        "french_horn": ReleaseProfile(0.080, 0.32, 0.025),
        "tuba": ReleaseProfile(0.105, 0.34, 0.030),
    }
)


@dataclass(frozen=True)
class ResonatorProfile:
    ratios: tuple[float, ...]
    amplitudes: tuple[float, ...]
    lifetimes: tuple[float, ...]
    strike: float
    tremolo: float = 0


RESONATORS = MappingProxyType(
    {
        "electric_piano": ResonatorProfile(
            (1, 2, 4.01, 7.03, 10.1),
            (1, 0.28, 0.22, 0.09, 0.025),
            (1, 0.65, 0.2, 0.1, 0.055),
            0.006,
            0.08,
        ),
        "xylophone": ResonatorProfile(
            (1, 3, 6, 10), (1, 0.45, 0.2, 0.08), (1, 0.45, 0.23, 0.12), 0.03
        ),
        "vibraphone": ResonatorProfile(
            (1, 4, 10, 16.8), (1, 0.22, 0.065, 0.02), (1, 0.7, 0.35, 0.2), 0.008, 0.24
        ),
        "glockenspiel": ResonatorProfile(
            (1, 2.756, 5.404, 8.933, 13.34),
            (1, 0.4, 0.23, 0.12, 0.05),
            (1, 0.7, 0.48, 0.3, 0.18),
            0.018,
        ),
        "toms": ResonatorProfile(
            (1, 1.594, 2.136, 2.296, 2.653, 2.918),
            (1, 0.4, 0.22, 0.12, 0.09, 0.07),
            (1, 0.72, 0.52, 0.37, 0.28, 0.2),
            0.055,
        ),
        "congas": ResonatorProfile(
            (1, 1.5, 2.05, 2.65, 3.4), (1, 0.55, 0.27, 0.13, 0.08), (1, 0.8, 0.5, 0.28, 0.17), 0.085
        ),
        "bongos": ResonatorProfile(
            (1, 1.59, 2.14, 2.65, 3.12),
            (1, 0.48, 0.25, 0.15, 0.08),
            (1, 0.6, 0.42, 0.26, 0.14),
            0.11,
        ),
        "timpani": ResonatorProfile(
            (1, 1.5, 2, 2.48, 2.95, 3.48),
            (1, 0.55, 0.3, 0.18, 0.1, 0.07),
            (1, 0.85, 0.6, 0.42, 0.28, 0.18),
            0.035,
        ),
    }
)
