"""Fixed source-level trims, independent of pitch, velocity, seed and note length.

Basis: examples/instrument_balance.py, dry one-second notes at three useful
registers and velocities .35/.65/1.0, 44.1 kHz. Compare active-window/onset RMS
within roles, then retain transient headroom. These deliberately partial trims
reduce conspicuous outliers; they do not promise equal perceived loudness.
Unlisted voices retain their designed levels, including all percussion/kit routes.
"""

from types import MappingProxyType

# dB, rounded conservatively: no automated inverse-RMS or near-silence boosts.
SOURCE_TRIM_DB = MappingProxyType(
    {
        # Sustained basic sources were 5–10 dB above typical sustained peers.
        "sine": -6.0,
        "triangle": -4.0,
        "pad": -3.0,
        "sub_bass": -3.0,
        "theremin": -3.0,
        # Flute/recorder exceeded the reed group by approximately 4–5 dB.
        "flute": -3.0,
        "recorder": -3.0,
        # Quiet struck/plucked sources: only part of the RMS gap is corrected
        # because their short decays and large crest factors are intentional.
        "piano": 4.0,
        "banjo": 3.0,
        "harpsichord": 3.0,
        "mandolin": 2.0,
        # Maximum-brightness low notes limit this voice to a 1 dB lift.
        "trance_pluck": 1.0,
        # Quiet legacy harmonic synthesizer compared with other synth leads.
        "synthesizer": 3.0,
    }
)
SOURCE_GAINS = MappingProxyType({name: 10 ** (db / 20) for name, db in SOURCE_TRIM_DB.items()})
