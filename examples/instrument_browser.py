"""Build the local catalog player: uv run python examples/instrument_browser.py."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import wave
from html import escape
from importlib.metadata import version
from pathlib import Path

import numpy as np

from audio_as_code import Note, Song, Track, export_midi, instrument_catalog, render
from audio_as_code.instruments import KIT_NOTES, InstrumentInfo, list_instruments

if __package__:
    from .famous_music import music_score, performance_settings
else:
    from famous_music import music_score, performance_settings

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("music", "phrase", "note")
SUSTAINED_FAMILIES = {"woodwinds", "brass", "bowed_strings"}
SUSTAINED_VOICES = {
    "organ",
    "pad",
    "sine",
    "theremin",
    "synthesizer",
    "supersaw",
    "string_machine",
    "wavetable_pad",
    "hoover",
    "sync_lead",
}
# Every clip is rendered to one loudness target so switching voices does not jump in level.
LOUDNESS_TARGET_LUFS = -16.0
PEAK_CEILING_DBFS = -1.5
# Noise-based hits overshoot between samples; a lower sample-peak ceiling keeps their
# true peak under -1 dBTP.
PERCUSSION_PEAK_CEILING_DBFS = -3.5


def loudness_settings(instrument: InstrumentInfo | None = None) -> dict:
    """Use the loudness target when the optional backend is installed."""
    try:
        import pyloudnorm  # noqa: F401
    except ImportError:
        return {}
    percussive = instrument is not None and instrument.midi_note is not None
    ceiling = PERCUSSION_PEAK_CEILING_DBFS if percussive else PEAK_CEILING_DBFS
    return {"target_lufs": LOUDNESS_TARGET_LUFS, "peak_ceiling_dbfs": ceiling}


def preview_score(instrument: InstrumentInfo, variant: str) -> Song:
    if variant not in {"note", "phrase"}:
        raise ValueError("Preview variant must be 'note' or 'phrase'")
    if instrument.midi_note is not None:
        starts = [0] if variant == "note" else [0, 1, 2, 2.5, 3, 4, 5, 5.5, 6]
        duration = {"kick": 0.65, "snare": 0.38, "hat": 0.13}.get(instrument.id, 0.85)
        if instrument.id in {"cymbal", "tambourine"}:
            starts = [0] if variant == "note" else [0, 3]
            duration = 3.5
        kit_pitches = list(KIT_NOTES)
        notes = [
            Note(
                pitch=kit_pitches[index % len(kit_pitches)]
                if instrument.id == "drum_machine"
                else instrument.midi_note,
                start=start,
                duration=min(duration, starts[index + 1] - start - 0.01)
                if index + 1 < len(starts)
                else duration,
                velocity=0.55 if index % 3 == 1 else 0.85,
            )
            for index, start in enumerate(starts)
        ]
        bpm, beats = 112, 4 if variant == "note" else 8
        score_label = "One hit" if variant == "note" else "Rhythm preview"
    else:
        root = {"bass": 36, "guitar": 52}.get(instrument.id, instrument.preview_pitch)
        if variant == "note":
            notes = [Note(pitch=root, duration=3, velocity=0.72)]
            beats = 4
        else:
            # Repeat the tonic at two touch levels, rise through the register,
            # leave a breath, then answer with a descending tonic cadence.
            offsets = [0, 0, 2, 4, 7, 5, 2, 0]
            if instrument.family in {"plucked_strings", "keyboards", "pitched_percussion"}:
                offsets[4] = 12
            starts = [0, 0.75, 1.5, 2.25, 3, 4.25, 5, 5.75]
            durations = [0.58, 0.58, 0.62, 0.62, 1.0, 0.62, 0.62, 1.6]
            if instrument.family in SUSTAINED_FAMILIES or instrument.id in SUSTAINED_VOICES:
                # Legato: each note holds until the next onset, then the cadence rings.
                durations = [0.75, 0.75, 0.75, 0.75, 1.25, 0.75, 0.75, 1.6]
            velocities = [0.45, 0.75, 0.57, 0.64, 0.82, 0.68, 0.59, 0.52]
            notes = [
                Note(
                    pitch=root + offset,
                    start=start,
                    duration=duration,
                    velocity=velocity,
                )
                for offset, start, duration, velocity in zip(
                    offsets, starts, durations, velocities, strict=True
                )
            ]
            beats = 8.3
        bpm = 96
        score_label = "Single note" if variant == "note" else "Touch, breath and cadence"
    return Song(
        title=f"{instrument.name} / {score_label}",
        bpm=bpm,
        beats=beats,
        seed=2026,
        sample_rate=44100,
        tracks=[
            Track(
                name=instrument.name,
                instrument=instrument.id,
                gain=0.85,
                notes=notes,
                **performance_settings(instrument.id),
            )
        ],
    )


def waveform(path: Path, bars: int = 72) -> list[float]:
    with wave.open(str(path), "rb") as stream:
        pcm = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2")
        samples = np.abs(pcm.astype(np.float32).reshape(-1, stream.getnchannels())).max(axis=1)
    peaks = np.array([part.max(initial=0) for part in np.array_split(samples, bars)])
    maximum = peaks.max(initial=0)
    return np.round(peaks / maximum, 4).tolist() if maximum else [0.0] * bars


def engine_fingerprint() -> str:
    """Include real DSP/source bytes and numeric runtime, not just a package version."""
    digest = hashlib.sha256()
    files = [
        *sorted((ROOT / "src/audio_as_code").glob("*.py")),
        Path(__file__),
        ROOT / "examples/famous_music.py",
        ROOT / "examples/music/excerpts.json",
    ]
    for path in files:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    digest.update(
        json.dumps(
            {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "mido": version("mido"),
                "pydantic": version("pydantic"),
                "platform": platform.platform(),
            },
            sort_keys=True,
        ).encode()
    )
    return digest.hexdigest()


def render_fingerprint(song: Song, engine: str) -> str:
    payload = json.dumps(song.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((engine + payload).encode()).hexdigest()


def artifact_paths(stem: str) -> dict[str, str]:
    return {
        "audio": f"audio/{stem}.wav",
        "score": f"scores/{stem}.json",
        "midi": f"midi/{stem}.mid",
        "report": f"reports/{stem}.json",
    }


def cached_preview(entry: dict, output: Path, stem: str, fingerprint: str) -> dict | None:
    if not isinstance(entry, dict):
        return None
    if entry.get("fingerprint") != fingerprint or not isinstance(entry.get("preview"), dict):
        return None
    paths = artifact_paths(stem)
    for kind, relative in paths.items():
        path = output / relative
        if not path.is_file():
            return None
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("sha256", {}).get(kind):
            return None
    if any(entry["preview"].get(kind) != relative for kind, relative in paths.items()):
        return None
    return entry["preview"]


def _write_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


# Fields the page needs; catalog.json beside it keeps the full reports and waveforms.
PAGE_CLIP_FIELDS = (
    "audio",
    "score",
    "midi",
    "seconds",
    "bpm",
    "notes",
    "title",
    "composer",
    "arrangement",
    "performers",
    "source",
    "credit",
    "license",
)


def _page_payload(data: dict) -> dict:
    previews = {}
    for instrument_id, clips in data.get("previews", {}).items():
        previews[instrument_id] = {}
        for variant, clip in clips.items():
            slim = {key: clip[key] for key in PAGE_CLIP_FIELDS if key in clip}
            # One base-36 digit per bar: ~72 bytes instead of ~500 per waveform.
            slim["wave"] = "".join(
                np.base_repr(round(min(max(float(peak), 0.0), 1.0) * 35), 36).lower()
                for peak in clip.get("waveform", [])
            )
            previews[instrument_id][variant] = slim
    return {**data, "previews": previews}


def _static_list(data: dict) -> str:
    """Names and WAV links in the HTML itself, for readers without JavaScript."""
    rows = []
    for item in data["instruments"]:
        clip = data.get("previews", {}).get(item["id"], {}).get("music")
        link = f' <a href="{escape(clip["audio"])}">WAV</a>' if clip else ""
        rows.append(f"<li>{escape(item['name'])} <code>{escape(item['id'])}</code>{link}</li>")
    return '<noscript><ul class="static-list">' + "".join(rows) + "</ul></noscript>"


def write_gallery_html(output: Path, data: dict) -> Path:
    """Write only index.html from catalog data: no rendering, no cache or catalog changes."""
    payload = json.dumps(_page_payload(data), ensure_ascii=True, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c")
    template = (ROOT / "web" / "instrument-browser.html").read_text(encoding="utf-8")
    for placeholder in ("__INSTRUMENT_DATA__", "__STATIC_LIST__"):
        if template.count(placeholder) != 1:
            raise RuntimeError(f"The HTML template must have exactly one {placeholder}")
    html = template.replace("__STATIC_LIST__", _static_list(data))
    html = html.replace("__INSTRUMENT_DATA__", payload)
    output.mkdir(parents=True, exist_ok=True)
    page = output / "index.html"
    page.write_text(html, encoding="utf-8")
    return page


def main(
    output: Path | None = None, *, instruments: list[str] | None = None, resume: bool = False
) -> dict:
    output = output or ROOT / "output" / "instruments"
    available = list_instruments()
    requested = set(instruments) if instruments is not None else {info.id for info in available}
    unknown = requested - {info.id for info in available}
    if unknown:
        raise ValueError(f"Unknown or unimplemented instruments: {', '.join(sorted(unknown))}")
    output.mkdir(parents=True, exist_ok=True)
    engine = engine_fingerprint()
    cache_path = output / "render-cache.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    entries = cache.get("clips", {})
    if not isinstance(entries, dict):
        entries = {}
    catalog = instrument_catalog(include_planned=True)
    previews, missing = {}, []
    rendered = reused = 0
    for instrument in available:
        clips = {}
        for variant in VARIANTS:
            metadata = {}
            if variant == "music":
                song, metadata = music_score(instrument)
            else:
                song = preview_score(instrument, variant)
            stem = f"{instrument.id}-{variant}"
            fingerprint = render_fingerprint(
                song, engine + json.dumps(loudness_settings(instrument))
            )
            previous = cached_preview(entries.get(stem, {}), output, stem, fingerprint)
            if previous is not None and (resume or instrument.id not in requested):
                clips[variant] = previous
                reused += 1
                continue
            if instrument.id not in requested:
                entries.pop(stem, None)
                missing.append(stem)
                continue
            paths = artifact_paths(stem)
            wav = output / paths["audio"]
            song.save(output / paths["score"])
            midi = export_midi(song, output / paths["midi"])
            report = render(song, wav, **loudness_settings(instrument))
            if report["wav"]["silent"] or report["wav"]["full_scale_samples"]:
                raise RuntimeError(f"Invalid preview audio: {stem}")
            report.update(midi=midi, render_fingerprint=fingerprint, provenance=metadata)
            report_path = output / paths["report"]
            report_path.parent.mkdir(parents=True, exist_ok=True)
            _write_json(report_path, report)
            clips[variant] = {
                **paths,
                "seconds": report["wav"]["duration_seconds"],
                "waveform": waveform(wav),
                "bpm": song.bpm,
                "notes": sum(len(track.notes) for track in song.tracks),
                "levels": report["wav"],
                "render_fingerprint": fingerprint,
                **metadata,
            }
            entries[stem] = {
                "fingerprint": fingerprint,
                "preview": clips[variant],
                "sha256": {
                    kind: hashlib.sha256((output / path).read_bytes()).hexdigest()
                    for kind, path in paths.items()
                },
            }
            # Save after each completed clip so an interrupted long batch can resume.
            _write_json(cache_path, {"version": 1, "engine_fingerprint": engine, "clips": entries})
            rendered += 1
        if clips:
            previews[instrument.id] = clips
        if instrument.id in requested:
            print(f"Ready {instrument.name}: {', '.join(clips)}", flush=True)
    if engine_fingerprint() != engine:
        raise RuntimeError("Engine or demo sources changed during rendering; rerun with --resume")
    build = {
        "engine_fingerprint": engine,
        "complete": not missing,
        "rendered": rendered,
        "reused": reused,
        "missing_previews": missing,
    }
    data = {**catalog, "previews": previews, "build": build}
    write_gallery_html(output, data)
    _write_json(output / "catalog.json", data)
    _write_json(cache_path, {"version": 1, "engine_fingerprint": engine, "clips": entries})
    print(f"Rendered {rendered}, reused {reused}, missing {len(missing)} clips", flush=True)
    print(f"Open: {output / 'index.html'}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=ROOT / "output/instruments")
    parser.add_argument(
        "--instruments", nargs="+", help="Render only these playable instrument IDs"
    )
    parser.add_argument(
        "--resume", action="store_true", help="Reuse only exact verified render inputs"
    )
    parser.add_argument(
        "--html-only",
        action="store_true",
        help="Rewrite index.html from the existing catalog.json without rendering audio",
    )
    args = parser.parse_args()
    if args.html_only:
        catalog_data = json.loads((args.output / "catalog.json").read_text(encoding="utf-8"))
        print(f"Open: {write_gallery_html(args.output, catalog_data)}")
    else:
        main(args.output, instruments=args.instruments, resume=args.resume)
