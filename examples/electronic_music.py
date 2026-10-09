"""Complete classical edition in four dance arrangements, plus dry voice auditions.

Run: uv run --extra loudness python examples/electronic_music.py
Open output/electronic-music/index.html. All audio is synthesized locally.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path

from audio_as_code import (
    Chorus,
    Delay,
    Distortion,
    Ducker,
    Filter,
    Note,
    Phaser,
    Reverb,
    Song,
    Tone,
    Track,
    export_midi,
    get_instrument,
    render,
)
from audio_as_code.electronic import ELECTRONIC_INSTRUMENTS

ROOT = Path(__file__).resolve().parents[1]
STYLES = {
    "disco": (118, ("string_machine", "clavinet", "electric_guitar", "bass_guitar")),
    "techno": (132, ("sync_lead", "wavetable_pad", "fm_bell", "sub_bass")),
    "trance": (138, ("supersaw", "string_machine", "trance_pluck", "sub_bass")),
    "drum-and-bass": (174, ("fm_bell", "wavetable_pad", "hoover", "reese_bass")),
}
PARTS = ("soprano", "alto", "tenor", "bass")
# Song form around the complete source: an 8-bar intro, then the 16-bar hymn
# (bars 1-8 full groove, bars 9-12 a kick-free breakdown, bars 13-16 the drop),
# then a 4-bar outro whose last chord rings out.
INTRO_BEATS = 32
OUTRO_BEATS = 16
LOUDNESS_TARGET_LUFS = -16.0
PEAK_CEILING_DBFS = -1.5
# Dry noise-based drum hits overshoot between samples; a lower ceiling keeps them
# under -1 dBTP.
DRUM_PEAK_CEILING_DBFS = -3.5
TONIC = 43  # G2: the hymn edition is in G major.

# Per style and part: (octave transpose, gain, pan, release seconds).
PART_MIX = {
    "disco": {
        "soprano": (12, 0.5, 0.0, 0.32),
        "alto": (0, 0.3, -0.35, 0.12),
        "tenor": (0, 0.26, 0.35, 0.1),
        "bass": (-12, 0.42, 0.0, 0.1),
    },
    "techno": {
        "soprano": (0, 0.42, 0.0, 0.22),
        "alto": (0, 0.24, -0.3, 0.6),
        "tenor": (12, 0.22, 0.3, 0.3),
        "bass": (-24, 0.26, 0.0, 0.08),
    },
    "trance": {
        "soprano": (12, 0.4, 0.0, 0.4),
        "alto": (0, 0.24, -0.3, 0.7),
        "tenor": (12, 0.3, 0.3, 0.3),
        "bass": (-24, 0.22, 0.0, 0.1),
    },
    "drum-and-bass": {
        "soprano": (12, 0.48, 0.0, 0.5),
        "alto": (0, 0.24, -0.3, 0.8),
        "tenor": (-12, 0.2, 0.3, 0.2),
        "bass": (-12, 0.34, 0.0, 0.1),
    },
}
# Short descriptions used on the listening page.
STYLE_NOTES = {
    "disco": "String-machine lead, slap bass, octave disco bass, clap and open hats.",
    "techno": "Sync lead over a 16th-note acid line, sub bass and a driving 909 grid.",
    "trance": "Supersaw lead with sidechain pump, offbeat bass and a snare-roll build.",
    "drum-and-bass": "Two-step break at 174 BPM, reese and sub bass, FM bell lead.",
}


def source_piece() -> dict:
    return json.loads((ROOT / "examples/music/classics-full.json").read_text(encoding="utf-8"))[
        "ode_to_joy"
    ]


def song_sections(style: str) -> list[tuple[str, float, float]]:
    """Named sections in beats, used for the page's section map."""
    s0, n = INTRO_BEATS, source_piece()["beats"]
    return [
        ("Intro", 0, s0),
        ("Theme", s0, s0 + 32),
        ("Breakdown", s0 + 32, s0 + 48),
        ("Drop", s0 + 48, s0 + n),
        ("Outro", s0 + n, s0 + n + OUTRO_BEATS),
    ]


def _bars(start: float, stop: float) -> range:
    return range(int(start), int(stop), 4)


def _hits(name: str, instrument: str, gain: float, rows, pan: float = 0.0, **extra) -> Track:
    pitch = get_instrument(instrument).preview_pitch
    unique = {}
    for start, duration, velocity in rows:
        unique.setdefault(round(start, 4), (start, duration, velocity))
    ordered = sorted(unique.values())
    notes = [
        Note(
            pitch=pitch,
            start=s,
            # Gate each hit before the next one so drum notes never overlap.
            duration=min(d, ordered[i + 1][0] - s - 0.01) if i + 1 < len(ordered) else d,
            velocity=round(v, 3),
        )
        for i, (s, d, v) in enumerate(ordered)
    ]
    return Track(name=name, instrument=instrument, gain=gain, pan=pan, notes=notes, **extra)


def _bass_root(rows: list, source_beat: float) -> int:
    """Lowest source bass pitch sounding at a source beat, folded into the G1 to F#2 octave."""
    sounding = [p for p, s, d, _ in rows if s <= source_beat < s + d]
    pitch = min(sounding) if sounding else TONIC
    while pitch > 42:
        pitch -= 12
    while pitch < 31:
        pitch += 12
    return pitch


def _velocity(source_beat: float, end: float) -> float:
    """Downbeat accents and a phrase arc; the final phrase is the loudest."""
    accent = 0.08 if source_beat % 4 == 0 else (0.03 if source_beat % 2 == 0 else 0)
    arc = 0.05 * math.sin(math.pi * (source_beat % 16) / 16)
    lift = 0.06 if source_beat >= end - 16 else 0
    return round(min(0.95, 0.62 + accent + arc + lift), 3)


def genre_song(style: str) -> Song:
    """Wrap the complete four-part hymn in an intro, breakdown, drop and outro.

    Every source note keeps its written duration and its onset (shifted by
    INTRO_BEATS); pitches move only by octaves. Drum, groove-bass and pad parts
    are original procedural parts, not sampled breakbeats or loops.
    """
    piece = source_piece()
    bpm, voices = STYLES[style]
    src_end = piece["beats"]
    s0 = INTRO_BEATS
    full_a = (s0, s0 + 32)
    drop = (s0 + 48, s0 + src_end)
    outro = (s0 + src_end, s0 + src_end + OUTRO_BEATS)
    end = outro[1]
    intro_groove = (0, s0) if style == "techno" else (16, s0)
    groove_spans = [intro_groove, full_a, drop, (outro[0], outro[0] + 8)]
    beat_seconds = 60 / bpm

    def in_spans(beat: float, spans) -> bool:
        return any(a <= beat < b for a, b in spans)

    kick_bar = (0.0, 2.5) if style == "drum-and-bass" else (0.0, 1.0, 2.0, 3.0)
    kicks = [
        float(bar + o) for bar in _bars(0, end) for o in kick_bar if in_spans(bar + o, groove_spans)
    ]
    kicks.append(float(outro[0] + 8))
    duck = Ducker(trigger_beats=kicks, depth=0.5, release_seconds=round(beat_seconds * 0.45, 3))

    tracks: list[Track] = []
    for part, instrument in zip(PARTS, voices, strict=True):
        transpose, gain, pan, release = PART_MIX[style][part]
        notes = [
            Note(
                pitch=pitch + transpose,
                start=start + s0,
                duration=duration,
                velocity=_velocity(start, src_end),
                articulation=("pop" if start % 2 == 1 else "slap")
                if instrument == "bass_guitar"
                else None,
            )
            for pitch, start, duration, _ in piece["parts"][part]
        ]
        effects: list = []
        tone = None
        if instrument == "string_machine":
            tone = Tone(brightness=0.55, detune_cents=14)
            effects = [Chorus(mix=0.3), Reverb(mix=0.22, decay_seconds=1.8), duck]
        elif instrument == "wavetable_pad":
            effects = [Chorus(mix=0.3), Reverb(mix=0.3, decay_seconds=2.4), duck]
        elif instrument == "clavinet":
            effects = [Phaser(mix=0.3, depth=0.6, rate_hz=0.25), Reverb(mix=0.1)]
        elif instrument == "electric_guitar":
            effects = [Chorus(mix=0.2), Reverb(mix=0.1)]
        elif instrument == "supersaw":
            tone = Tone(brightness=0.62, detune_cents=20)
            effects = [
                Chorus(mix=0.2),
                Delay(time_seconds=beat_seconds * 0.75, mix=0.16, repeats=3),
                Reverb(mix=0.22, decay_seconds=2.2),
                duck,
            ]
        elif instrument == "sync_lead":
            tone = Tone(brightness=0.5, glide_seconds=0.04)
            effects = [
                Delay(time_seconds=beat_seconds * 0.75, mix=0.2, repeats=4),
                Reverb(mix=0.16, decay_seconds=1.6),
            ]
        elif instrument == "trance_pluck":
            effects = [Delay(time_seconds=beat_seconds * 0.75, mix=0.25, repeats=4), Reverb()]
        elif instrument == "fm_bell":
            tone = Tone(fm_ratio=2, fm_index=1.4, decay_seconds=1.6)
            effects = [Delay(time_seconds=beat_seconds * 0.75, repeats=3, mix=0.18), Reverb()]
        elif instrument == "hoover":
            effects = [Distortion(drive=2.0, mix=0.15), duck]
        elif instrument == "reese_bass":
            effects = [Distortion(drive=2.4, mix=0.2), duck]
        elif instrument == "sub_bass":
            effects = [duck]
        elif instrument == "bass_guitar":
            tone = Tone(brightness=0.45)
        tracks.append(
            Track(
                name=part,
                instrument=instrument,
                notes=notes,
                gain=gain,
                pan=pan,
                release_seconds=release,
                tone=tone,
                effects=effects,
            )
        )

    # The drop doubles the melody on a second voice so the payoff is audibly bigger.
    double_voice, double_shift, double_gain = {
        "disco": ("clavinet", 0, 0.4),
        "techno": ("supersaw", 0, 0.24),
        "trance": ("trance_pluck", 12, 0.32),
        "drum-and-bass": ("supersaw", -12, 0.28),
    }[style]
    tracks.append(
        Track(
            name="Drop lead double",
            instrument=double_voice,
            gain=double_gain,
            pan=0.12,
            release_seconds=0.2,
            notes=[
                Note(
                    pitch=p + PART_MIX[style]["soprano"][0] + double_shift,
                    start=s + s0,
                    duration=d,
                    velocity=_velocity(s, src_end),
                )
                for p, s, d, _ in piece["parts"]["soprano"]
                if s + s0 >= drop[0]
            ],
            effects=[Delay(time_seconds=beat_seconds * 0.75, mix=0.15, repeats=3), duck],
        )
    )

    # Groove bass: the source bass line re-voiced as each genre's bass figure.
    figure = {
        "disco": [(0.0, 0), (0.5, 12), (1.0, 0), (1.5, 12)],
        "techno": [(i / 4, 12 if i % 4 == 2 else 0) for i in range(8)],
        "trance": [(0.5, 0), (1.5, 0)],
        "drum-and-bass": [(0.0, 0)],
    }[style]
    length = {"disco": 0.4, "techno": 0.2, "trance": 0.42, "drum-and-bass": 1.9}[style]
    groove = []
    for bar in _bars(0, outro[0]):
        for half in (0.0, 2.0):
            for offset, octave in figure:
                beat = bar + half + offset
                if not in_spans(beat, groove_spans):
                    continue
                source_beat = beat - s0
                root = TONIC if source_beat < 0 else _bass_root(piece["parts"]["bass"], source_beat)
                groove.append(
                    Note(
                        pitch=root + octave + (12 if style in {"disco", "techno"} else 0),
                        start=beat,
                        duration=length,
                        velocity=0.85 if offset in (0.0, 0.5) else 0.68,
                        articulation="accented"
                        if style == "techno" and round(offset * 4) % 3 == 0
                        else None,
                    )
                )
    tracks.append(
        Track(
            name="Groove bass",
            instrument={
                "disco": "disco_bass",
                "techno": "acid_bass",
                "trance": "disco_bass",
                "drum-and-bass": "sub_bass",
            }[style],
            gain={"disco": 0.48, "techno": 0.4, "trance": 0.52, "drum-and-bass": 0.42}[style],
            notes=groove,
            tone=Tone(cutoff_hz=700, resonance=0.6, filter_env_octaves=2.5)
            if style == "techno"
            else None,
            release_seconds=0.05,
            effects=[duck] if style != "drum-and-bass" else [],
        )
    )

    # Pad: an opening G major chord that opens its filter across the intro, and
    # a closing chord with a long release so the piece ends on a natural tail.
    pad_notes = [
        Note(pitch=pitch, start=start, duration=duration, velocity=velocity)
        for start, duration, velocity in ((0, s0, 0.55), (outro[0], 12, 0.7))
        for pitch in (55, 62, 67, 71)
    ]
    tracks.append(
        Track(
            name="Intro and outro pad",
            instrument="wavetable_pad"
            if style in {"techno", "drum-and-bass"}
            else "string_machine",
            gain=0.2,
            release_seconds=2.5,
            notes=pad_notes,
            effects=[
                Filter(
                    cutoff_hz=500,
                    end_cutoff_hz=6000,
                    sweep_seconds=round(beat_seconds * s0, 3),
                ),
                Chorus(mix=0.3),
                Reverb(mix=0.35, decay_seconds=3.0),
            ],
        )
    )
    tracks.append(
        Track(
            name="Outro bass",
            instrument="sub_bass",
            gain=0.12,
            release_seconds=1.5,
            notes=[Note(pitch=TONIC, start=outro[0], duration=12, velocity=0.8)],
        )
    )

    # Drums.
    kick_voice = "kick_808" if style == "drum-and-bass" else "kick_909"
    tracks.append(
        _hits(
            "Kick",
            kick_voice,
            0.62,
            [(b, 0.5, 0.95 if b % 4 == 0 else 0.88) for b in kicks],
            tone=Tone(decay_seconds=0.7 if style == "drum-and-bass" else 0.45),
        )
    )
    backbeat = []
    for bar in _bars(0, end):
        for o in (1.0, 3.0):
            if in_spans(bar + o, groove_spans):
                backbeat.append((bar + o, 0.3, 0.92))
        if style == "drum-and-bass":
            for o, v in ((0.75, 0.32), (2.25, 0.28), (3.75, 0.38)):
                if in_spans(bar + o, groove_spans):
                    backbeat.append((bar + o, 0.1, v))
    # Build: a snare roll that thickens into the theme and into the drop.
    roll = []
    for target in (s0, drop[0]):
        roll += [(target - 4 + i * 0.25, 0.12, 0.3 + 0.5 * i / 11) for i in range(12)]
        roll += [(target - 1 + i * 0.125, 0.06, 0.8 + 0.12 * i / 7) for i in range(8)]
    if style in {"disco", "techno"}:
        tracks.append(_hits("Backbeat", "clap", 0.42, backbeat, pan=0.05))
        tracks.append(_hits("Build roll", "electronic_snare", 0.26, roll, pan=-0.1))
    else:
        # One MIDI drum note per instrument: the roll shares the backbeat snare track.
        tracks.append(_hits("Backbeat", "electronic_snare", 0.42, backbeat + roll, pan=0.05))
    hats = []
    for bar in _bars(0, outro[0] + 8):
        if bar < 8 and style != "techno":
            continue
        step = 0.25 if in_spans(bar, [full_a, drop]) and style != "drum-and-bass" else 0.5
        for i in range(int(4 / step)):
            beat = bar + i * step
            hats.append((beat, 0.1, 0.75 if beat % 1 == 0.5 else (0.42 if beat % 1 else 0.58)))
    tracks.append(_hits("Closed hats", "metal_hat", 0.9, hats, pan=0.2))
    if style == "drum-and-bass":
        ride = [
            (bar + i / 2, 0.5, 0.7 if i % 2 == 0 else 0.5)
            for bar in _bars(0, end)
            for i in range(8)
            if in_spans(bar + i / 2, [full_a, drop])
        ]
        tracks.append(_hits("Ride", "electronic_ride", 0.4, ride, pan=-0.25))
    else:
        opens = [
            (bar + o, 0.4, 0.75)
            for bar in _bars(0, end)
            for o in (0.5, 1.5, 2.5, 3.5)
            if in_spans(bar + o, [full_a, drop, (16, s0)])
        ]
        tracks.append(_hits("Open hats", "open_hat", 0.55, opens, pan=-0.2))
    crashes = [(b, 3.5, 0.85) for b in (s0, drop[0], outro[0])]
    tracks.append(_hits("Crash", "cymbal", 0.4, crashes, pan=-0.1))

    return Song(
        title=f"Ode to Joy / {style}",
        bpm=bpm,
        beats=end,
        seed=901,
        sample_rate=44100,
        master_gain=1.0,
        tracks=tracks,
        # Oversampled tanh soft clip on the bus: rounds drum transients so the
        # mix reaches the loudness target under the peak ceiling. Part of the score.
        effects=[Distortion(drive=3.0, mix=1.0)],
    )


def original_song() -> Song:
    piece = source_piece()
    return Song(
        title="Ode to Joy / original hymn edition",
        bpm=piece["bpm"],
        beats=piece["beats"],
        tracks=[
            Track(
                name=part,
                instrument="piano",
                gain=0.6 if part == "soprano" else 0.35,
                release_seconds=0.12,
                notes=[Note(pitch=p, start=s, duration=d, velocity=v) for p, s, d, v in rows],
            )
            for part, rows in piece["parts"].items()
        ],
    )


def audition_song(instrument: str) -> Song:
    """A dry two-bar figure: a groove for drums, a legato riff with a held note otherwise."""
    info = get_instrument(instrument)
    if info.midi_note is not None:
        pattern = {
            "kick_808": [(0, 0.9), (2.5, 0.8), (4, 0.9), (6.5, 0.8), (7, 0.6)],
            "kick_909": [(i, 0.9 if i % 2 == 0 else 0.8) for i in range(8)],
            "clap": [(1, 0.85), (3, 0.9), (5, 0.85), (7, 0.9), (7.75, 0.5)],
            "electronic_snare": [(1, 0.85), (3, 0.9), (4.75, 0.35), (5, 0.85), (7, 0.9)],
            "metal_hat": [(i / 2, 0.75 if i % 2 else 0.5) for i in range(16)],
            "open_hat": [(i + 0.5, 0.8) for i in range(8)],
            "electronic_ride": [(i / 2, 0.7 if i % 2 == 0 else 0.5) for i in range(16)],
            "fm_percussion": [(0, 0.8), (1.5, 0.55), (2.75, 0.7), (4, 0.8), (5.5, 0.6), (7, 0.7)],
        }.get(instrument, [(0, 0.85), (4, 0.4), (5.5, 0.85)])
        starts = [s for s, _ in pattern] + [8.0]
        notes = [
            Note(
                pitch=info.preview_pitch,
                start=start,
                duration=min(1.5, starts[i + 1] - start),
                velocity=velocity,
            )
            for i, (start, velocity) in enumerate(pattern)
        ]
        release = 0.12
    else:
        # Notes reach the next onset and the release overlaps it (legato); the last note holds.
        riff = ((0, 0, 0.55), (1, 0, 0.85), (2, 7, 0.7), (3, 12, 0.8), (4, 10, 0.65), (5, 7, 0.7))
        notes = [
            Note(pitch=info.preview_pitch + offset, start=i, duration=0.99, velocity=v)
            for i, offset, v in riff
        ]
        notes.append(Note(pitch=info.preview_pitch, start=6, duration=2.5, velocity=0.75))
        release = 0.45
    return Song(
        title=info.name,
        bpm=110,
        beats=10,
        seed=901,
        tracks=[
            Track(
                name=info.name,
                instrument=instrument,
                gain=0.7,
                notes=notes,
                release_seconds=release,
            )
        ],
    )


TEMPLATE = ROOT / "web" / "electronic-lab.html"


def _section_map(style: str, seconds: float, bpm: float) -> str:
    total_beats = song_sections(style)[-1][2]
    spans = "".join(
        f'<span class="s-{name.lower()}" style="width:{100 * (b - a) / total_beats:.3f}%">'
        f"{name}</span>"
        for name, a, b in song_sections(style)
    )
    return (
        f'<div class="map" role="slider" tabindex="0" aria-label="Seek in the arrangement" '
        f'aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">{spans}<i></i><b></b></div>'
    )


def _page(songs: dict, reports: dict, keys: list[str]) -> str:
    source = source_piece()
    cards, voices = [], []
    for key in keys:
        song, report = songs[key], reports[key]
        seconds = report["audio"]["duration_seconds"]
        title = html.escape(song.title, quote=True)
        links = (
            f'<p class="links"><a href="{key}.json">Editable score</a> · '
            f'<a href="{key}.wav">WAV</a> · <a href="{key}.mid">MIDI</a></p>'
        )
        audio = f'<audio preload="none" src="{key}.wav"></audio>'
        clock = f'<span class="time">0:00 / {fmt_time(seconds)}</span></div>'
        if key in STYLES:
            name = "Drum and bass" if key == "drum-and-bass" else key.capitalize()
            cards.append(
                f'<article class="card" data-player data-title="{title}" '
                f'data-seconds="{seconds:.2f}"><div class="card-top"><span class="label">'
                f"{song.bpm:g} BPM · {fmt_time(seconds)}</span>"
                f'<span class="label">Arrangement</span></div><h3>{html.escape(name)}</h3>'
                f"<p>{html.escape(STYLE_NOTES[key])}</p>"
                f'<div class="controls"><button class="play" type="button" data-play '
                f'aria-pressed="false" aria-label="Play {title}">Play</button>'
                f"{_section_map(key, seconds, song.bpm)}{clock}{audio}{links}</article>"
            )
        elif key == "original":
            cards.append(
                f'<article class="card original" data-player data-title="{title}" '
                f'data-seconds="{seconds:.2f}"><div class="card-top"><span class="label">'
                f"Reference · {song.bpm:g} BPM · {fmt_time(seconds)}</span></div>"
                "<h3>The hymn, as written</h3><p>The complete 16-bar, four-part edition on piano. "
                "Every arrangement above keeps all of these notes.</p>"
                f'<div class="controls"><button class="play" type="button" data-play '
                f'aria-pressed="false" aria-label="Play {title}">Play</button>'
                f"{clock}{audio}{links}</article>"
            )
        else:
            voices.append(
                f'<div class="voice" data-player data-title="{title}" data-seconds="{seconds:.2f}">'
                f'<button class="play" type="button" data-play aria-pressed="false" '
                f'aria-label="Play {title}">Play</button><div><strong>{html.escape(song.title)}'
                f'</strong><small><code>{html.escape(key)}</code> · <a href="{key}.json">score</a>'
                f' · <a href="{key}.wav">WAV</a></small></div>{audio}</div>'
            )
    lufs = [
        reports[k]["loudness"]["achieved_lufs"]
        for k in keys
        if k in STYLES
        and reports[k].get("loudness")
        and reports[k]["loudness"].get("achieved_lufs")
    ]
    loud = (
        f"The four arrangements measure {min(lufs):.1f} to {max(lufs):.1f} LUFS integrated. "
        if lufs
        else ""
    )
    original = next(c for c in cards if "card original" in c)
    arrangements = [c for c in cards if "card original" not in c]
    content = (
        '<section class="hero"><div><p class="kicker">Audio as Code / electronic lab</p>'
        "<h1>Ode to Joy, <span>four ways</span></h1>"
        '<p class="lede">One public-domain hymn, rebuilt as disco, techno, trance and drum and '
        "bass. Each arrangement has an intro, a breakdown, a drop and an outro, and every "
        "sound in it is synthesized from code.</p></div>"
        '<button class="start" type="button" data-start>Play disco first</button></section>'
        "<h2>The arrangements</h2>"
        '<p class="section-note">Click the section map to jump straight to the breakdown or the '
        "drop. Only one track plays at a time.</p>"
        '<section class="tracks" aria-label="Arrangements">'
        + "".join(arrangements)
        + original
        + "</section><h2>The voices</h2>"
        '<p class="section-note">Each electronic voice alone, dry, playing a short riff or a '
        "two-bar groove. These are the building blocks of the arrangements.</p>"
        '<section class="voices" aria-label="Voice auditions">'
        + "".join(voices)
        + '</section><section class="about"><div><h2>What you are hearing</h2>'
        "<p>The source is the complete 16-bar, four-part Ode to Joy hymn edition, not "
        "Beethoven's entire symphony. Every source note keeps its written rhythm; parts move "
        "only by octaves. The intro, outro, groove bass, pads and drums are new parts written "
        "for each genre.</p><p>All instruments are procedural synthesis models: no recordings, "
        "samples or loops. They are designed sounds, not replicas of specific hardware.</p>"
        "</div><div><h2>How it was measured</h2>"
        f"<p>Listening copies are rendered with a {LOUDNESS_TARGET_LUFS:g} LUFS target and a "
        f"{PEAK_CEILING_DBFS:g} dBFS sample-peak ceiling ({DRUM_PEAK_CEILING_DBFS:g} for dry drum "
        f"auditions). {loud}Short dry auditions can land "
        'below the target when the peak ceiling limits them. Exact numbers are in <a href="'
        'measurements.json">the render report</a>.</p><p>These are signal measurements; they '
        "do not prove how good the music sounds.</p></div></section>"
        '<footer>Source score: <a href="'
        + html.escape(source["source_url"], quote=True)
        + '">Mutopia edition</a>. '
        + html.escape(source["credit"])
        + ", Public Domain. MIDI keeps notes and tempo; external instruments and effects "
        "differ.</footer></main>"
    )
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count("__CONTENT__") != 1:
        raise RuntimeError("The electronic page template must have exactly one __CONTENT__")
    return template.replace("__CONTENT__", content)


def fmt_time(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def build(
    output: Path, *, loudness: bool = True, only: str | None = None, html_only: bool = False
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    songs = {"original": original_song(), **{style: genre_song(style) for style in STYLES}}
    songs.update({voice: audition_song(voice) for voice in sorted(ELECTRONIC_INSTRUMENTS)})
    for instrument, gestures in (
        ("bass_guitar", ("slap", "pop", "muted")),
        ("electric_guitar", ("muted",)),
    ):
        base = audition_song(instrument)
        songs[f"{instrument}-original"] = base
        for gesture in gestures:
            data = base.model_dump()
            data["title"] = f"{base.title} / {gesture}"
            data["tracks"][0]["articulation"] = gesture
            songs[f"{instrument}-{gesture}"] = Song.model_validate(data)
    if only is not None and only not in songs:
        raise ValueError(f"unknown audition {only!r}; choose from {', '.join(songs)}")
    measurements = output / "measurements.json"
    reports = (
        json.loads(measurements.read_text(encoding="utf-8"))
        if (html_only or only) and measurements.is_file()
        else {}
    )
    for key, song in songs.items():
        if html_only or (only is not None and key != only):
            continue
        score_path = output / f"{key}.json"
        score_path.write_text(song.model_dump_json(indent=2), encoding="utf-8")
        kwargs = (
            {
                "target_lufs": LOUDNESS_TARGET_LUFS,
                "peak_ceiling_dbfs": DRUM_PEAK_CEILING_DBFS
                if get_instrument(song.tracks[0].instrument).midi_note is not None
                and len(song.tracks) == 1
                else PEAK_CEILING_DBFS,
            }
            if loudness
            else {}
        )
        reports[key] = render(song, output / f"{key}.wav", **kwargs)
        export_midi(song, output / f"{key}.mid")
        print(f"Rendered {key}: {reports[key]['audio']['duration_seconds']:.2f}s", flush=True)
    if not html_only:
        measurements.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    keys = [
        key
        for key in songs
        if key in reports
        and all((output / f"{key}.{ext}").is_file() for ext in ("wav", "json", "mid"))
    ]
    (output / "index.html").write_text(_page(songs, reports, keys), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=ROOT / "output/electronic-music")
    parser.add_argument("--no-loudness", action="store_true", help="Use only the core dependencies")
    parser.add_argument("--only", help="Render one named style or voice into this output directory")
    parser.add_argument(
        "--html-only", action="store_true", help="Refresh the player from existing renders"
    )
    args = parser.parse_args()
    build(args.output, loudness=not args.no_loudness, only=args.only, html_only=args.html_only)
