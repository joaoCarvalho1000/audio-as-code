"""Deterministic, in-process synthesis. No audio device, API key, or DAW needed."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np

from ._audio import Audio, _metrics, _write_wav, analyze_wav
from ._export_rules import MAX_RENDER_SECONDS
from ._export_rules import note_frame as _note_frame
from ._paths import check_paths
from ._voices import _voice
from .automation import automation_values
from .effects import apply_effects
from .model import Song, Track, midi_pitch

PEAK_CEILING = 0.95


@dataclass(frozen=True)
class RenderResult:
    audio: Audio
    report: dict


def _note_seed(song_seed: int, track_name: str, note_index: int) -> int:
    """Track-local seeds keep noise unchanged when an unrelated track is added."""
    data = f"{song_seed}:{track_name}:{note_index}".encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "little")


def _track_audio(song: Song, track: Track, frames: int) -> Audio:
    if (
        song.tempo_map
        or song.automation
        or track.automation
        or any(effect.mix for effect in track.effects)
        or track.release_seconds
        or track.pedal
        or any(note.release_seconds for note in track.notes)
    ):
        return _expressive_track_audio(song, track, frames)
    result = np.zeros((frames, 2), dtype=np.float32)
    angle = (track.pan + 1) * np.pi / 4
    left, right = math.cos(angle), math.sin(angle)
    for index, note in enumerate(track.notes):
        start = _note_frame(song, note.start)
        end = min(frames, _note_frame(song, note.start + note.duration))
        if end <= start or track.gain == 0:
            continue
        seed = _note_seed(song.seed, track.name, index)
        voice = _voice(
            track.instrument,
            midi_pitch(note.pitch),
            end - start,
            song.sample_rate,
            seed,
            note.velocity,
            track.tone,
        )
        voice *= note.velocity * track.gain * song.master_gain
        result[start:end, 0] += voice * left
        result[start:end, 1] += voice * right
    return result


def _expressive_track_audio(song: Song, track: Track, frames: int) -> Audio:
    mono = np.zeros(frames, dtype=np.float32)
    for index, note in enumerate(track.notes):
        start = _note_frame(song, note.start)
        held_end = _note_frame(song, song.note_gate_end(track, note))
        release = song.note_release_seconds(track, note)
        end = min(frames, held_end + round(release * song.sample_rate))
        if held_end <= start:
            continue
        seed = _note_seed(song.seed, track.name, index)
        voice = _voice(
            track.instrument,
            midi_pitch(note.pitch),
            end - start,
            song.sample_rate,
            seed,
            note.velocity,
            track.tone,
            held_frames=held_end - start if end > held_end else None,
        )
        mono[start:end] += voice * note.velocity
    result = np.zeros((frames, 2), dtype=np.float32)
    lanes = {lane.parameter: lane for lane in track.automation}
    for start in range(0, frames, 65536):
        stop = min(frames, start + 65536)
        gain = (
            automation_values(song, lanes["gain"], start, stop) if "gain" in lanes else track.gain
        )
        pan = automation_values(song, lanes["pan"], start, stop) if "pan" in lanes else track.pan
        angle = (pan + 1) * np.pi / 4
        result[start:stop, 0] = mono[start:stop] * gain * np.cos(angle)
        result[start:stop, 1] = mono[start:stop] * gain * np.sin(angle)
    del mono
    result = apply_effects(result, track.effects, song.sample_rate)
    for start in range(0, frames, 65536):
        stop = min(frames, start + 65536)
        if song.automation:
            gain = automation_values(song, song.automation[0], start, stop)
            result[start:stop] *= gain[:, None]
        else:
            result[start:stop] *= song.master_gain
    return result


def _canonical_score(song: Song) -> dict:
    """Omit additive defaults from hashing to preserve existing score identities."""
    data = song.model_dump(mode="json")
    for key in ("tempo_map", "automation", "effects"):
        if not data[key]:
            del data[key]
    for track in data["tracks"]:
        for key in ("automation", "effects", "release_seconds", "pedal"):
            if not track[key]:
                del track[key]
        for note in track["notes"]:
            if note["release_seconds"] is None:
                del note["release_seconds"]
    return data


def render_audio(song: Song, *, normalize: bool = True) -> RenderResult:
    """Render stereo float32 audio and measurements. Limit: five minutes per call.

    Normalization only attenuates to a 0.95 peak ceiling; it never boosts a quiet mix.
    Floating-point output remains unclipped when normalization is disabled.
    """
    # Revalidate even if a caller used Pydantic's unchecked construction/copy escape hatches.
    song = Song.model_validate(song.model_dump())
    if song.render_seconds > MAX_RENDER_SECONDS:
        raise ValueError(f"offline renders are limited to {MAX_RENDER_SECONDS} seconds")
    frames = round(song.render_seconds * song.sample_rate)
    if frames < 1:
        raise ValueError("song is shorter than one audio sample")
    mix = np.zeros((frames, 2), dtype=np.float32)
    for track in song.tracks:
        mix += _track_audio(song, track, frames)
    mix = apply_effects(mix, song.effects, song.sample_rate)
    if not np.all(np.isfinite(mix)):
        raise ValueError("render produced non-finite samples; lower score gains or effect levels")
    before = _metrics(mix, song.sample_rate)
    attenuation = min(1.0, PEAK_CEILING / before["peak"]) if normalize and before["peak"] else 1.0
    mix *= attenuation
    warnings = []
    if before["silent"]:
        warnings.append("The render is silent; check notes, pitch range, and track/master gains.")
    if attenuation < 1:
        warnings.append(
            "The mix exceeded the peak ceiling and was attenuated; consider lowering gains."
        )
    if not normalize and before["clipped_samples"]:
        warnings.append("The mix exceeds full scale; WAV export will hard-clip these samples.")
    if any(
        _note_frame(song, song.note_gate_end(track, note)) - _note_frame(song, note.start) < 3
        for track in song.tracks
        for note in track.notes
    ):
        warnings.append("Some notes are too short for the audio sample grid and may be silent.")
    canonical = json.dumps(_canonical_score(song), sort_keys=True, separators=(",", ":"))
    report = {
        "engine_version": version("audio-as-code"),
        "numpy_version": np.__version__,
        "score_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "title": song.title,
        "tracks": len(song.tracks),
        "notes": sum(len(track.notes) for track in song.tracks),
        "seed": song.seed,
        "normalize": normalize,
        "score_duration_seconds": song.seconds,
        "tail_seconds": max(0.0, song.render_seconds - song.seconds),
        "effects": {
            "master": [effect.model_dump() for effect in song.effects],
            "tracks": {
                track.name: [effect.model_dump() for effect in track.effects]
                for track in song.tracks
                if track.effects
            },
        },
        "gain_applied": attenuation,
        "before_gain": before,
        "audio": _metrics(mix, song.sample_rate),
        "warnings": warnings,
    }
    return RenderResult(mix, report)


def render(
    song: Song, path: str | Path, *, normalize: bool = True, stems_dir: str | Path | None = None
) -> dict:
    """Write a 16-bit stereo WAV. Optional stems share the mix's attenuation."""
    song = Song.model_validate(song.model_dump())
    destination = Path(path)
    stem_paths = []
    if stems_dir is not None:
        # Use numeric filenames; track names never become filesystem paths.
        stem_paths = [Path(stems_dir) / f"{index + 1:02d}.wav" for index in range(len(song.tracks))]
    check_paths(
        [destination, *stem_paths],
        [stems_dir] if stems_dir is not None else [],
        conflict_message="mix and stem outputs must not have the same path or file",
    )
    result = render_audio(song, normalize=normalize)
    _write_wav(destination, result.audio, song.sample_rate)
    report = {**result.report, "output": str(destination), "stems": []}
    report["wav"] = analyze_wav(destination)
    if stem_paths and song.effects:
        report["warnings"].append(
            "Stems include track effects and master gain automation, but omit master effects; "
            "their sum will differ from the processed mix."
        )
    for track, stem_path in zip(song.tracks, stem_paths, strict=False):
        stem = _track_audio(song, track, len(result.audio))
        stem *= result.report["gain_applied"]
        _write_wav(stem_path, stem, song.sample_rate)
        metrics = _metrics(stem, song.sample_rate)
        report["stems"].append({"track": track.name, "path": str(stem_path), "audio": metrics})
        if metrics["clipped_samples"]:
            report["warnings"].append(f"Stem {track.name!r} exceeds full scale and was clipped.")
    return report
