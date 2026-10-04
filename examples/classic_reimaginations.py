"""AI-written arrangements of five complete public-domain score editions.

Run: uv run python examples/classic_reimaginations.py --ffmpeg ffmpeg
The runtime uses no model, recordings or downloaded audio. See the accompanying guide.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import wave
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np

from audio_as_code import Note, Reverb, Song, Tone, Track, export_midi, render

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "examples/music/classics-full.json"
PROVENANCE = {
    "arrangement_author": "AI agent",
    "model": "gpt-6-astra",
    "method": "Agent-written Python score transformation; deterministic procedural synthesis",
}
RECIPES = {
    "fur_elise": {
        "id": "classic-fur-elise",
        "title": "Elise After Midnight",
        "bpm": 78,
        "bar": 3,
        "seed": 3801,
        "master_gain": 1.0,
        "brief": "A familiar letter delivered by the last jazz tram: intimate, sly, then luminous.",
        "arrangement": "Complete piano score recast as electric-piano/celesta lead handoffs, "
        "harp accompaniment, source-derived bass and a restrained three-beat drum groove.",
        "parts": {"right": ("electric_piano", "celesta"), "left": ("harp",)},
    },
    "cello_prelude": {
        "id": "classic-cello-prelude",
        "title": "The Clockwork Aquarium",
        "bpm": 96,
        "bar": 4,
        "seed": 3802,
        "master_gain": 1.0,
        "brief": "Bach's entire river of notes becomes a glass aquarium full of tiny machines.",
        "arrangement": "Every cello event moves up an octave to marimba; bass anchors, sparse "
        "kalimba glints and an evolving clockwork pulse reveal the source's harmonic motion.",
        "parts": {"cello": ("marimba",)},
    },
    "turkish_march": {
        "id": "classic-turkish-march",
        "title": "The Royal Arcade",
        "bpm": 128,
        "bar": 2,
        "seed": 3803,
        "master_gain": 1.0,
        "brief": "Mozart wins the final level: bright mallets, a nimble bass "
        "and a royal dance floor.",
        "arrangement": "The complete repeated form alternates xylophone and mandolin lead, "
        "electric-piano left hand, nimble bass roots and a dance pulse with a central breakdown.",
        "parts": {"right": ("xylophone", "mandolin"), "left": ("electric_piano",)},
    },
    "greensleeves": {
        "id": "classic-greensleeves",
        "title": "Greensleeves on Europa",
        "bpm": 82,
        "bar": 3,
        "seed": 3804,
        "master_gain": 1.0,
        "brief": "A Renaissance tune heard through the window of an ice-moon observatory.",
        "arrangement": "Theremin and an octave-higher recorder answer across the complete melody "
        "above the source's harp harmony, low bass pedals, sparse bell glints and generated space.",
        "parts": {"melody": ("theremin", "recorder"), "harmony": ("harp",)},
    },
    "ode_to_joy": {
        "id": "classic-ode-to-joy",
        "title": "Joy at the Lunar Funfair",
        "bpm": 116,
        "bar": 4,
        "seed": 3805,
        "master_gain": 1.0,
        "track_gain_scale": 1.05,
        "brief": "A moon-rover parade discovers Beethoven: plucky, buoyant, gloriously earnest.",
        "arrangement": "All sixteen hymn bars and four voices become banjo/clarinet lead "
        "handoffs, electric-piano alto, harp tenor and bass guitar, plus a light parade beat.",
        "parts": {
            "soprano": ("banjo", "clarinet"),
            "alto": ("electric_piano",),
            "tenor": ("harp",),
            "bass": ("bass_guitar",),
        },
    },
}


def pieces() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def _role(key: str, part: str, start: float) -> tuple[str, int]:
    recipe = RECIPES[key]
    voices = recipe["parts"][part]
    voice = voices[int(start // (recipe["bar"] * 8)) % len(voices)]
    transpose = 12 if key == "cello_prelude" or voice == "recorder" else 0
    return voice, transpose


def _gate_events(events: list[tuple], end: float) -> list[Note]:
    """Merge exact unisons and stop repeated keys before retriggering for MIDI."""
    merged: dict[tuple[float, int], tuple[float, float]] = {}
    for pitch, start, duration, velocity in events:
        previous = merged.get((start, pitch), (0.0, 0.0))
        merged[start, pitch] = (max(duration, previous[0]), max(velocity, previous[1]))
    notes, next_start = [], {}
    for (start, pitch), (duration, velocity) in sorted(merged.items(), reverse=True):
        duration = min(duration, end - start, next_start.get(pitch, end + 1) - start)
        if duration < 1 / 480:
            raise ValueError(f"Note too short for MIDI at {start}: {pitch}")
        notes.append(Note(pitch=pitch, start=start, duration=duration, velocity=velocity))
        next_start[pitch] = start
    return sorted(notes, key=lambda note: (note.start, note.pitch))


def _tone(voice: str) -> Tone | None:
    if voice == "theremin":
        return Tone(brightness=0.36, vibrato_depth_cents=9, vibrato_rate_hz=4.5)
    if voice == "clarinet":
        return Tone(brightness=0.4, breath=0.06)
    if voice == "bass_guitar":
        return Tone(brightness=0.3, decay_seconds=1.3)
    if voice == "celesta":
        return Tone(brightness=0.38, decay_seconds=2.7)
    if voice == "kalimba":
        return Tone(brightness=0.48, decay_seconds=1.9)
    if voice == "mandolin":
        return Tone(brightness=0.46, decay_seconds=1.7, pluck_position=0.2, detune_cents=5)
    if voice == "recorder":
        return Tone(brightness=0.42, breath=0.045, vibrato_depth_cents=2, vibrato_rate_hz=4.8)
    if voice in {"harp", "electric_piano", "vibraphone", "marimba", "banjo"}:
        return Tone(brightness=0.42, decay_seconds=1.5)
    return None


def _release(voice: str) -> float:
    return {
        "celesta": 0.18,
        "kalimba": 0.14,
        "mandolin": 0.1,
        "recorder": 0.04,
        "electric_piano": 0.13,
        "vibraphone": 0.18,
        "harp": 0.17,
        "marimba": 0.09,
        "xylophone": 0.06,
        "glockenspiel": 0.2,
        "bass_guitar": 0.07,
        "theremin": 0.065,
        "clarinet": 0.045,
        "banjo": 0.085,
    }.get(voice, 0)


def _source_tracks(key: str, source: dict) -> tuple[list[Track], list[dict]]:
    lanes: dict[tuple[str, str, int], list[tuple]] = defaultdict(list)
    counts: dict[tuple[str, str, int], int] = defaultdict(int)
    for part, rows in source["parts"].items():
        if part not in RECIPES[key]["parts"]:
            raise ValueError(f"Unmapped complete source part: {key}/{part}")
        for pitch, start, duration, velocity in rows:
            voice, transpose = _role(key, part, start)
            lane = (part, voice, transpose)
            bar = RECIPES[key]["bar"]
            phrase_position = (start % (bar * 4)) / (bar * 4)
            phrase = 0.90 + 0.12 * math.sin(math.pi * phrase_position)
            pulse = 1.035 if start % bar < 0.03 else 0.985
            arc = 0.97 + 0.03 * math.sin(math.pi * start / max(source["beats"], 1))
            expressive_velocity = min(0.90, max(0.20, velocity * phrase * pulse * arc))
            lanes[lane].append((pitch + transpose, start, duration, expressive_velocity))
            counts[lane] += 1
    tracks, mapping = [], []
    lead_part = next(iter(RECIPES[key]["parts"]))
    for (part, voice, transpose), rows in lanes.items():
        lead = part == lead_part
        gain = 0.48 if lead else 0.27
        if lead:
            gain = {"electric_piano": 0.52, "celesta": 0.43, "marimba": 0.52, "mandolin": 0.57}.get(
                voice, gain
            )
        if voice in {"theremin", "clarinet"}:
            gain = 0.22
        if voice == "bass_guitar":
            gain = 0.36
        if voice == "recorder":
            gain = 0.36
        name = f"Source {part} - {voice}"
        notes = _gate_events(rows, source["beats"])
        actual = {(note.pitch, note.start) for note in notes}
        expected = {(pitch, start) for pitch, start, _length, _velocity in rows}
        if actual != expected:
            raise RuntimeError(f"Incomplete source coverage in {name}")
        tracks.append(
            Track(
                name=name,
                instrument=voice,
                gain=gain,
                pan={"celesta": 0.15, "recorder": 0.15, "mandolin": 0.12}.get(
                    voice, -0.04 if lead else -0.22
                ),
                tone=_tone(voice),
                release_seconds=_release(voice),
                notes=notes,
            )
        )
        mapping.append(
            {
                "track": name,
                "source_parts": [part],
                "instrument": voice,
                "transpose_semitones": transpose,
                "source_events": counts[part, voice, transpose],
                "arranged_events": len(notes),
                "pitch_onset_coverage": "complete",
            }
        )
    if sum(item["source_events"] for item in mapping) != sum(
        len(rows) for rows in source["parts"].values()
    ):
        raise RuntimeError("Source event accounting failed")
    return tracks, mapping


def _root_pitch(rows: list, start: float, stop: float) -> int:
    candidates = [row for row in rows if start <= row[1] < stop]
    if not candidates:
        candidates = [row for row in rows if row[1] <= start][-1:]
    first = min(row[1] for row in candidates)
    pitch = min(row[0] for row in candidates if row[1] == first)
    while pitch < 36:
        pitch += 12
    while pitch > 52:
        pitch -= 12
    return pitch


def _added_tracks(key: str, source: dict) -> list[Track]:
    recipe, end = RECIPES[key], source["beats"]
    bar = recipe["bar"]
    low_part = {"fur_elise": "left", "turkish_march": "left", "greensleeves": "harmony"}
    rows = source["parts"].get(low_part.get(key, "cello"), [])
    bass, sparkle, drums = [], [], []
    for bar_index, start in enumerate(range(0, math.ceil(end), bar)):
        available = min(bar, end - start)
        fraction = start / end
        # Sparse opening, fuller second phrase, central breathing space, final lift.
        dense = 0.18 <= fraction < 0.48 or 0.72 <= fraction < 0.94
        if rows and key != "ode_to_joy":
            root = _root_pitch(rows, start, start + available)
            bass.append((root, start, max(0.1, available * 0.78), 0.57 if dense else 0.43))
            if dense and key == "turkish_march" and available > 1.5:
                bass[-1] = (root, start, 0.7, 0.6)
                bass.append((root, start + 1, 0.7, 0.48))
            if key in {"cello_prelude", "greensleeves"} and bar_index % 4 == 3:
                # Kalimba stays in its central register; the source's low Bach
                # line remains on marimba rather than being forced onto lamellae.
                register = 24 if key == "cello_prelude" else 36
                sparkle.append((root + register, start, min(available, 1.8), 0.42))
        if key == "greensleeves" or start + bar >= end or bar_index < 2:
            continue
        if not dense and bar_index % 2:
            continue
        if key == "fur_elise":
            hits = [(36, 0, 0.52), (42, 1, 0.3), (38, 2, 0.29)]
        elif key == "cello_prelude":
            hits = [(42, i * 0.5, 0.25 if i % 2 else 0.36) for i in range(8)]
            if dense:
                hits += [(36, 0, 0.42), (45, 3, 0.26)]
        elif key == "turkish_march":
            hits = [(36, 0, 0.57), (38, 1, 0.43), (42, 0.5, 0.28), (42, 1.5, 0.33)]
        else:
            hits = [(36, 0, 0.54), (38, 1, 0.42), (36, 2, 0.4), (38, 3, 0.48)]
            if dense:
                hits += [(42, i + 0.5, 0.24) for i in range(4)]
        drums += [
            (p, start + offset, 0.13, v) for p, offset, v in hits if offset + 0.13 < available
        ]
    result = []
    for name, voice, events, gain, pan in [
        ("Added harmonic anchors", "bass_guitar", bass, 0.27, 0),
        (
            "Added phrase glints",
            "kalimba" if key == "cello_prelude" else "glockenspiel",
            sparkle,
            0.23 if key == "cello_prelude" else 0.18,
            0.4,
        ),
        ("Added changing groove", "drum_machine", drums, 0.25, 0),
    ]:
        if events:
            result.append(
                Track(
                    name=name,
                    instrument=voice,
                    gain=gain,
                    pan=pan,
                    tone=_tone(voice),
                    release_seconds=_release(voice),
                    notes=_gate_events(events, end),
                )
            )
    return result


def arrange(key: str, source: dict | None = None) -> tuple[Song, list[dict]]:
    source = source or pieces()[key]
    recipe = RECIPES[key]
    tracks, mapping = _source_tracks(key, source)
    tracks += _added_tracks(key, source)
    tracks = [
        Track.model_validate(
            {**track.model_dump(), "gain": track.gain * recipe.get("track_gain_scale", 1.0)}
        )
        for track in tracks
    ]
    song = Song(
        title=recipe["title"],
        bpm=recipe["bpm"],
        beats=source["beats"] + 1.5,
        sample_rate=44100,
        seed=recipe["seed"],
        master_gain=recipe["master_gain"],
        tracks=tracks,
        effects=[Reverb(mix=0.10, decay_seconds=0.7)] if key == "greensleeves" else [],
    )
    if song.render_seconds > 300:
        raise ValueError("Reimagining exceeds the complete render limit")
    return song, mapping


def _source_bundle(destination: Path) -> None:
    paths = [
        Path(__file__).resolve(),
        DATASET,
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        ROOT / "LICENSE",
        ROOT / "README.md",
        ROOT / "docs/classic-reimaginations.md",
        *sorted((ROOT / "src/audio_as_code").glob("*.py")),
        *sorted((ROOT / "src/audio_as_code/_project_templates").glob("*.txt")),
        ROOT / "src/audio_as_code/_project_templates/score.json",
        ROOT / "src/audio_as_code/py.typed",
    ]
    shutil.copyfile(__file__, destination / "classic_reimaginations.py")
    (destination / "music").mkdir(exist_ok=True)
    shutil.copyfile(DATASET, destination / "music/classics-full.json")
    with zipfile.ZipFile(
        destination / "classic-reimaginations-source.zip", "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in paths:
            archive.write(path, "audio-as-code-reimaginations/" + path.relative_to(ROOT).as_posix())


def _end_metrics(path: Path) -> dict:
    with wave.open(str(path)) as wav:
        rate, frames = wav.getframerate(), wav.getnframes()
        wav.setpos(max(0, frames - rate))
        audio = np.frombuffer(wav.readframes(rate), dtype="<i2").astype(np.float64) / 32768
    return {
        "last_second_rms": float(np.sqrt(np.mean(audio**2))),
        "last_sample_peak": float(np.max(np.abs(audio[-2:]))),
    }


def export_all(
    destination: str | Path, *, ffmpeg: str | None = None, scores_only: bool = False
) -> list[dict]:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    encoder = ffmpeg or shutil.which("ffmpeg")
    if not scores_only and not encoder:
        raise ValueError("Supply an installed FFmpeg with --ffmpeg PATH for MP3 previews")
    # A listening manifest may refer only to a completed coherent export. Keep
    # existing audio files, but do not advertise them after rewriting their scores.
    (destination / "manifest.json").unlink(missing_ok=True)
    _source_bundle(destination)
    exported = []
    sources = pieces()
    for key, recipe in RECIPES.items():
        source = sources[key]
        song, mapping = arrange(key, source)
        piece_id = recipe["id"] + "-reimagined"
        song.save(destination / f"{piece_id}.json")
        if Song.load(destination / f"{piece_id}.json") != song:
            raise RuntimeError(f"Score round-trip failed: {piece_id}")
        midi = export_midi(song, destination / f"{piece_id}.mid")
        if scores_only:
            print(f"Validated complete score and MIDI: {piece_id}", flush=True)
            continue
        print(
            f"Rendering {piece_id}: {song.render_seconds:.2f}s, "
            f"{sum(len(t.notes) for t in song.tracks)} notes",
            flush=True,
        )
        wav, mp3 = destination / f"{piece_id}.wav", destination / f"{piece_id}.mp3"
        report = render(song, wav)
        metrics = report["wav"]
        if (
            metrics["silent"]
            or metrics["full_scale_samples"]
            or not all(
                math.isfinite(metrics[field]) for field in ("peak", "rms", "duration_seconds")
            )
            or metrics["duration_seconds"] > 300
        ):
            raise RuntimeError(f"Invalid audio output: {piece_id}")
        end = _end_metrics(wav)
        if end["last_sample_peak"] > 0.001:
            raise RuntimeError(f"Abrupt ending: {piece_id}")
        report.update(source_mapping=mapping, midi=midi, ending=end, provenance=PROVENANCE)
        (destination / f"{piece_id}.report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        subprocess.run(
            [
                encoder,
                "-v",
                "error",
                "-y",
                "-i",
                str(wav),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(mp3),
            ],
            check=True,
        )
        subprocess.run([encoder, "-v", "error", "-i", str(mp3), "-f", "null", "-"], check=True)
        sections = [dict(section) for section in source["sections"]]
        sections.append(
            {
                "name": "Let it settle",
                "start_beat": source["beats"],
                "end_beat": song.render_seconds * song.bpm / 60,
            }
        )
        exported.append(
            {
                "id": piece_id,
                "pair_id": recipe["id"],
                "reimagines": recipe["id"],
                "variant": "reimagined",
                "work_title": source["title"],
                "title": song.title,
                "description": recipe["arrangement"],
                "brief": recipe["brief"],
                "bpm": song.bpm,
                "beats": song.beats,
                "duration_seconds": metrics["duration_seconds"],
                "instruments": list(dict.fromkeys(t.instrument for t in song.tracks)),
                "sections": sections,
                "wav": wav.name,
                "preview": mp3.name,
                "midi": f"{piece_id}.mid",
                "score": f"{piece_id}.json",
                "report": f"{piece_id}.report.json",
                "source": "classic_reimaginations.py",
                "source_bundle": "classic-reimaginations-source.zip",
                "source_dependencies": ["music/classics-full.json"],
                "source_function": "arrange",
                "code_excerpt": f'arrange("{key}")',
                "seed": song.seed,
                "sample_rate": song.sample_rate,
                "tracks": len(song.tracks),
                "notes": sum(len(t.notes) for t in song.tracks),
                "levels": metrics,
                "warnings": report["warnings"],
                "composer": source["composer"],
                "source_url": source["source_url"],
                "source_license": source["license"],
                "edition_credit": source["credit"],
                "complete": True,
                "excerpt": False,
                "scope": source["scope"],
                "arrangement": recipe["arrangement"],
                "agent_arranged": True,
                "provenance": PROVENANCE,
                "source_mapping": mapping,
                "source_piece": key,
                "source_beats": source["beats"],
                "source_bpm": source["bpm"],
                "repeat_expansion": source.get("repeat_expansion", []),
                "source_dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
                "arrangement_notes": "All source pitch/onset events mapped; "
                "exact duplicate unisons merge and same-pitch gates stop at retriggers. "
                "Octave shifts are declared per track. Four-bar dynamic contours and short "
                "voice-specific release envelopes shape the written source gates. "
                "Added bass, glints and percussion "
                "are accompaniment, not source-note replacements. Fixed tempo, no sampled "
                "instruments; only Greensleeves uses subtle generated reverb.",
            }
        )
        print(f"Finished {piece_id}: peak {metrics['peak']:.4f}", flush=True)
    if not scores_only:
        (destination / "manifest.json").write_text(
            json.dumps({"pieces": exported}, indent=2) + "\n", encoding="utf-8"
        )
    return exported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="output/classic-reimaginations")
    parser.add_argument("--ffmpeg", help="Installed FFmpeg executable")
    parser.add_argument("--scores-only", action="store_true")
    args = parser.parse_args()
    export_all(args.output, ffmpeg=args.ffmpeg, scores_only=args.scores_only)
