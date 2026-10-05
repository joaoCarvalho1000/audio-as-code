"""Dry catalog audit: python examples/instrument_balance.py --label before.

Run again after a synthesis change with --label after --compare before. Reports,
fixed-gain auditions and an A/B page stay under ignored output/instrument-balance.
This contributor diagnostic uses internal voice dispatch to measure mono sources
before pan, track gain, effects or master normalization. It is not a loudness matcher.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

import numpy as np

from audio_as_code import Ducker, Note, Song, Track, render_audio
from audio_as_code._audio import _write_wav
from audio_as_code._voices import _voice
from audio_as_code.instruments import KIT_NOTES, InstrumentInfo, list_instruments
from audio_as_code.loudness import measure_loudness

if __package__:
    from .electronic_music import STYLES, genre_song
else:
    from electronic_music import STYLES, genre_song

ROOT = Path(__file__).resolve().parents[1]
VELOCITIES = (0.35, 0.65, 1.0)
# Useful bass registers rather than extrapolating below a string's lowest note.
REGISTERS = {
    "guitar": (40, 55, 72),
    "bass_guitar": (28, 40, 52),
    "banjo": (50, 62, 74),
    "bass": (28, 40, 52),
    "reese_bass": (28, 40, 52),
    "fm_bass": (28, 40, 52),
    "sub_bass": (28, 40, 52),
}


def pitches_for(info: InstrumentInfo) -> tuple[int, ...]:
    if info.id == "drum_machine":
        return tuple(KIT_NOTES)
    if info.midi_note is not None:
        return (info.midi_note,)
    return REGISTERS.get(
        info.id, (info.preview_pitch - 12, info.preview_pitch, info.preview_pitch + 12)
    )


def db(value: float) -> float | None:
    return float(20 * np.log10(value)) if value > 0 else None


def metrics(audio: np.ndarray, rate: int) -> dict:
    """RMS over active 20 ms blocks; retain onset and duration as context.

    Activity threshold: 30 dB below the strongest block, with an absolute -60
    dBFS floor. Silent/near-silent notes have null RMS, never an inferred boost.
    Stereo RMS uses mean channel energy; peaks inspect both channels.
    """
    x = audio.astype(np.float64)
    energy = x**2 if x.ndim == 1 else np.mean(x**2, axis=1)
    block = round(0.02 * rate)
    powers = energy[: len(energy) // block * block].reshape(-1, block).mean(axis=1)
    active = powers >= max(float(powers.max(initial=0)) * 0.001, 1e-6)
    rms = float(np.sqrt(powers[active].mean())) if active.any() else 0.0
    peak = float(np.max(np.abs(x), initial=0))
    return {
        "active_rms_dbfs": db(rms),
        "onset_400ms_rms_dbfs": db(float(np.sqrt(energy[: round(0.4 * rate)].mean()))),
        "peak_dbfs": db(peak),
        "crest_db": db(peak / rms) if rms else None,
        "active_seconds": float(active.sum() * block / rate),
        "finite": bool(np.isfinite(x).all()),
        "full_scale_samples": int(np.count_nonzero(np.abs(x) >= 1)),
    }


def mixed_scores(rate: int) -> dict[str, Song]:
    """First four bars of unchanged dance arrangements, plus equal-gain ensembles."""
    scores = {}
    for style in STYLES:
        song = genre_song(style)
        tracks = []
        for track in song.tracks:
            notes = [
                n.model_copy(update={"duration": min(n.duration, 16 - n.start)})
                for n in track.notes
                if n.start < 16
            ]
            effects = tuple(
                effect.model_copy(
                    update={"trigger_beats": tuple(b for b in effect.trigger_beats if b < 16)}
                )
                if isinstance(effect, Ducker)
                else effect
                for effect in track.effects
            )
            tracks.append(track.model_copy(update={"notes": tuple(notes), "effects": effects}))
        scores[style] = song.model_copy(
            update={"beats": 16, "sample_rate": rate, "automation": (), "tracks": tuple(tracks)}
        )
    for name, voices in {
        "winds": (("flute", 72), ("clarinet", 64), ("oboe", 67), ("bassoon", 48)),
        "plucked": (("piano", 60), ("mandolin", 67), ("harp", 55), ("banjo", 62)),
    }.items():
        scores[name] = Song(
            title=name,
            bpm=120,
            beats=8,
            seed=2026,
            sample_rate=rate,
            master_gain=0.8,
            tracks=[
                Track(
                    name=instrument,
                    instrument=instrument,
                    gain=0.3,
                    notes=[
                        Note(pitch=pitch + offset, start=i, duration=0.9, velocity=0.65)
                        for i, offset in enumerate((0, 2, 4, 0, 7, 4, 2, 0))
                    ],
                )
                for instrument, pitch in voices
            ],
        )
    return scores


def write_page(output: Path, label: str, compare: str | None, clips: list[str]) -> None:
    labels = [compare, label] if compare else [label]
    rows = []
    for clip in clips:
        players = "".join(
            f'<td>{escape(item)}<br><audio controls preload="none" '
            f'src="{escape(item)}/{escape(clip)}.wav"></audio></td>'
            for item in labels
        )
        rows.append(f"<tr><th>{escape(clip)}</th>{players}</tr>")
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Instrument balance</title>'
        "<style>body{font:16px system-ui;margin:2rem;max-width:1100px}td,th{padding:.7rem;"
        "text-align:left}audio{width:330px}th{font-weight:500}</style>"
        "<h1>Instrument balance A/B</h1><p>Unmatched comparison: all files use the same "
        "fixed playback gain (0.7). "
        "No peak or loudness normalization. Keep device volume unchanged. Solo clips play "
        "low/middle/high registers, each at velocity 0.35, 0.65, 1.0; drums use their fixed "
        "pitch and the kit cycles its eight routes. Notes last one second with 0.15 s gaps. "
        "Mixes retain original score gains. Gain-matching solos would cancel the fixed trims "
        "and is deliberately not applied. Measurements do not establish perceived balance "
        "or realism; short percussion and sub-bass need listening in context.</p><table>"
        + "".join(rows)
        + '</table><script>document.addEventListener("play", e => { '
        'document.querySelectorAll("audio").forEach(a => {if(a !== e.target) a.pause()}); '
        "}, true)</script></html>",
        encoding="utf-8",
    )


def audit(output: Path, label: str, compare: str | None, rate: int, loudness: bool) -> dict:
    if label not in {"before", "after"} or compare not in {None, "before", "after"}:
        raise ValueError("audit labels must be 'before' or 'after'")
    if compare == label:
        raise ValueError("comparison label must differ from the new run; keep the baseline")
    if compare:
        baseline = json.loads((output / compare / "report.json").read_text(encoding="utf-8"))
        if baseline["sample_rate"] != rate:
            raise ValueError("comparison must use the same sample rate as the baseline")
    destination = output / label
    destination.mkdir(parents=True, exist_ok=True)
    rows, clips, mixes = [], [], {}
    for info in list_instruments():
        sequence = []
        for pitch in pitches_for(info):
            for velocity in VELOCITIES:
                x = _voice(info.id, pitch, rate, rate, 2026, velocity) * velocity
                row = {
                    "instrument": info.id,
                    "family": info.family,
                    "pitch": pitch,
                    "velocity": velocity,
                    **metrics(x, rate),
                }
                if loudness:
                    row["integrated_lufs"] = measure_loudness(x, rate)["integrated_lufs"]
                rows.append(row)
                sequence.extend((x, np.zeros(round(rate * 0.15), dtype=np.float32)))
        mono = np.concatenate(sequence) * (0.7 / np.sqrt(2))
        _write_wav(destination / f"{info.id}.wav", np.column_stack((mono, mono)), rate)
        clips.append(info.id)
        print(f"Audited {info.id}", flush=True)
    for name, song in mixed_scores(rate).items():
        result = render_audio(song, normalize=False)
        stems = {}
        for track in song.tracks:
            solo = render_audio(song.model_copy(update={"tracks": (track,)}), normalize=False)
            stems[track.name] = {"instrument": track.instrument, **metrics(solo.audio, rate)}
        mixes[name] = {"audio": metrics(result.audio, rate), "stems": stems}
        if loudness:
            mixes[name]["integrated_lufs"] = measure_loudness(result.audio, rate)["integrated_lufs"]
        _write_wav(destination / f"mix-{name}.wav", result.audio * 0.7, rate)
        clips.append(f"mix-{name}")
        print(f"Audited mix {name}", flush=True)
    report = {
        "sample_rate": rate,
        "seed": 2026,
        "note_seconds": 1,
        "playback_gain": 0.7,
        "measurement": (
            "Dry mono including velocity; active 20ms blocks, -30dB relative/-60dBFS floor"
        ),
        "rows": rows,
        "mixes": mixes,
    }
    (destination / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_page(output, label, compare, clips)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/instrument-balance")
    parser.add_argument("--label", choices=("before", "after"), default="after")
    parser.add_argument("--compare", choices=("before", "after"))
    parser.add_argument("--sample-rate", type=int, choices=(22050, 44100, 48000), default=44100)
    parser.add_argument("--loudness", action="store_true", help="Include optional BS.1770 LUFS")
    args = parser.parse_args()
    audit(args.output, args.label, args.compare, args.sample_rate, args.loudness)
