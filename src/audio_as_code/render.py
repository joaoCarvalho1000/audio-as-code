"""Deterministic, in-process synthesis. No audio device, API key, or DAW needed."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np

from ._audio import Audio, WavFormat, _metrics, _validate_wav_format, _write_wav, analyze_wav
from ._export_rules import MAX_RENDER_SECONDS
from ._export_rules import note_frame as _note_frame
from ._paths import check_paths
from ._render_control import (
    CancelCallback,
    ProgressCallback,
    RenderCancelled,
    RenderProgress,
    _RenderControl,
    _staged_outputs,
)
from ._voices import _voice
from .automation import automation_values
from .effects import apply_effects
from .loudness import _loudness_gain, _validate_target, measure_loudness
from .model import Song, Track, midi_pitch

PEAK_CEILING = 0.95

__all__ = [
    "RenderCancelled",
    "RenderProgress",
    "RenderResult",
    "WavFormat",
    "analyze_wav",
    "render",
    "render_audio",
    "render_preview",
    "render_preview_audio",
]


@dataclass(frozen=True)
class RenderResult:
    audio: Audio
    report: dict


def _note_seed(song_seed: int, track_name: str, note_index: int) -> int:
    """Track-local seeds keep noise unchanged when an unrelated track is added."""
    data = f"{song_seed}:{track_name}:{note_index}".encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "little")


def _track_audio(
    song: Song, track: Track, frames: int, control: _RenderControl | None = None
) -> Audio:
    if (
        song.tempo_map
        or song.automation
        or track.automation
        or any(effect.mix for effect in track.effects)
        or track.release_seconds
        or track.pedal
        or any(note.release_seconds for note in track.notes)
    ):
        return _expressive_track_audio(song, track, frames, control)
    result = np.zeros((frames, 2), dtype=np.float32)
    angle = (track.pan + 1) * np.pi / 4
    left, right = math.cos(angle), math.sin(angle)
    for index, note in enumerate(track.notes):
        if control is not None:
            control.notify("notes", index, len(track.notes), track.name)
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
            articulation=note.articulation or track.articulation,
        )
        voice *= note.velocity * track.gain * song.master_gain
        result[start:end, 0] += voice * left
        result[start:end, 1] += voice * right
    return result


def _expressive_track_audio(
    song: Song, track: Track, frames: int, control: _RenderControl | None = None
) -> Audio:
    mono = np.zeros(frames, dtype=np.float32)
    for index, note in enumerate(track.notes):
        if control is not None:
            control.notify("notes", index, len(track.notes), track.name)
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
            articulation=note.articulation or track.articulation,
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
    if control is not None:
        control.notify("track_effects", 0, 1, track.name)
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
        if track["articulation"] is None:
            del track["articulation"]
        for key in ("automation", "effects", "release_seconds", "pedal"):
            if not track[key]:
                del track[key]
        for note in track["notes"]:
            if note["articulation"] is None:
                del note["articulation"]
            if note["release_seconds"] is None:
                del note["release_seconds"]
    return data


def render_audio(
    song: Song,
    *,
    normalize: bool = True,
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
    target_lufs: float | None = None,
    peak_ceiling_dbfs: float = -1.0,
) -> RenderResult:
    """Render stereo float32 audio and measurements. Limit: five minutes per call.

    Default normalization only attenuates to a 0.95 sample-peak ceiling. An optional
    target_lufs instead applies a measured loudness gain, bounded by
    peak_ceiling_dbfs; this can boost quiet audio and requires the loudness extra.
    Floating-point output remains unclipped when normalization is disabled.
    Progress counts are stage-local. Cancellation is checked between notes and
    processing stages; a running voice or effect operation cannot be interrupted.
    """
    return _render_audio(
        song,
        normalize=normalize,
        control=_RenderControl(progress, cancel),
        target_lufs=target_lufs,
        peak_ceiling_dbfs=peak_ceiling_dbfs,
    )


def _render_audio(
    song: Song,
    *,
    normalize: bool,
    control: _RenderControl,
    target_lufs: float | None = None,
    peak_ceiling_dbfs: float = -1.0,
) -> RenderResult:
    # Revalidate even if a caller used Pydantic's unchecked construction/copy escape hatches.
    song = Song.model_validate(song.model_dump())
    if song.render_seconds > MAX_RENDER_SECONDS:
        raise ValueError(f"offline renders are limited to {MAX_RENDER_SECONDS} seconds")
    frames = round(song.render_seconds * song.sample_rate)
    if frames < 1:
        raise ValueError("song is shorter than one audio sample")
    _validate_target(target_lufs, peak_ceiling_dbfs, normalize, song.sample_rate, frames)
    control.notify("tracks", 0, len(song.tracks))
    mix = np.zeros((frames, 2), dtype=np.float32)
    for index, track in enumerate(song.tracks):
        mix += _track_audio(song, track, frames, control)
        control.notify("tracks", index + 1, len(song.tracks), track.name)
    control.notify("master_effects", 0, 1)
    mix = apply_effects(mix, song.effects, song.sample_rate)
    control.notify("analysis", 0, 1)
    if not np.all(np.isfinite(mix)):
        raise ValueError("render produced non-finite samples; lower score gains or effect levels")
    before = _metrics(mix, song.sample_rate)
    attenuation = min(1.0, PEAK_CEILING / before["peak"]) if normalize and before["peak"] else 1.0
    loudness = None
    if target_lufs is not None:
        control.notify("loudness", 0, 2)
        attenuation, loudness = _loudness_gain(
            mix, song.sample_rate, target_lufs, peak_ceiling_dbfs
        )
        control.notify("loudness", 1, 2)
    mix *= attenuation
    warnings = []
    if before["silent"]:
        warnings.append("The render is silent; check notes, pitch range, and track/master gains.")
    if attenuation < 1 and target_lufs is None:
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
    if loudness is not None:
        after = measure_loudness(mix, song.sample_rate)["integrated_lufs"]
        loudness["integrated_lufs"] = after
        loudness["measurable"] = after is not None
        loudness["achieved_lufs"] = after
        loudness["target_reached"] = after is not None and abs(after - target_lufs) <= 0.1
        report["loudness"] = loudness
        if loudness["before_lufs"] is None:
            warnings.append(
                "Loudness is below the measurement gate; no loudness boost was applied."
            )
        elif loudness["peak_limited"]:
            warnings.append(
                "The sample-peak ceiling limited loudness gain; the target may not be reached."
            )
        elif not loudness["target_reached"]:
            warnings.append(
                "Measured loudness differs from the target after gating; see achieved_lufs."
            )
        control.notify("loudness", 2, 2)
    control.notify("analysis", 1, 1)
    return RenderResult(mix, report)


def render(
    song: Song,
    path: str | Path,
    *,
    normalize: bool = True,
    stems_dir: str | Path | None = None,
    wav_format: WavFormat = "pcm16",
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
    target_lufs: float | None = None,
    peak_ceiling_dbfs: float = -1.0,
) -> dict:
    """Write stereo WAV (pcm16 default, pcm24, or float32), with optional stems.

    Stems share mix attenuation. Float exports preserve finite overs above 1.0.
    Files are staged before publication; each replacement is atomic, but a
    filesystem failure during publication can replace only part of a stem set.
    """
    song = Song.model_validate(song.model_dump())
    _validate_wav_format(wav_format)
    control = _RenderControl(progress, cancel)
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
    result = _render_audio(
        song,
        normalize=normalize,
        control=control,
        target_lufs=target_lufs,
        peak_ceiling_dbfs=peak_ceiling_dbfs,
    )
    report = {**result.report, "output": str(destination), "stems": []}
    _format_report(report, wav_format)
    if stem_paths and song.effects:
        report["warnings"].append(
            "Stems include track effects and master gain automation, but omit master effects; "
            "their sum will differ from the processed mix."
        )
    with _staged_outputs([destination, *stem_paths]) as staged:
        control.notify("export", 0, len(staged))
        _write_wav(staged[0], result.audio, song.sample_rate, wav_format)
        report["wav"] = analyze_wav(staged[0])
        control.notify("export", 1, len(staged))
        for index, (track, stem_path) in enumerate(zip(song.tracks, stem_paths, strict=False)):
            stem = _track_audio(song, track, len(result.audio), control)
            stem *= result.report["gain_applied"]
            _write_wav(staged[index + 1], stem, song.sample_rate, wav_format)
            metrics = _metrics(stem, song.sample_rate)
            report["stems"].append({"track": track.name, "path": str(stem_path), "audio": metrics})
            if metrics["clipped_samples"]:
                ending = "preserved in float WAV." if wav_format == "float32" else "was clipped."
                report["warnings"].append(f"Stem {track.name!r} exceeds full scale and {ending}")
            control.notify("export", index + 2, len(staged))
    return report


def _format_report(report: dict, wav_format: WavFormat) -> None:
    if wav_format != "pcm16":
        report["wav_format"] = wav_format
    if wav_format == "float32":
        report["warnings"] = [
            warning.replace(
                "WAV export will hard-clip these samples.",
                "float WAV preserves these samples above full scale.",
            )
            for warning in report["warnings"]
        ]


def _preview_bounds(song: Song, start_seconds: float, duration_seconds: float) -> tuple[int, int]:
    for value, name in ((start_seconds, "start_seconds"), (duration_seconds, "duration_seconds")):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{name} must be a finite number")
    if start_seconds < 0 or duration_seconds <= 0:
        raise ValueError("preview start must be nonnegative and duration must be positive")
    frames = round(song.render_seconds * song.sample_rate)
    if start_seconds >= song.render_seconds:
        raise ValueError("preview starts at or beyond the rendered song end")
    start = round(start_seconds * song.sample_rate)
    # Clip in seconds before multiplication so huge finite durations stay bounded.
    end = round(min(song.render_seconds, start_seconds + duration_seconds) * song.sample_rate)
    if start >= frames or end <= start:
        raise ValueError("preview is shorter than one audio sample")
    return start, end


def _preview_result(
    song: Song,
    start_seconds: float,
    duration_seconds: float,
    normalize: bool,
    control: _RenderControl,
    target_lufs: float | None,
    peak_ceiling_dbfs: float,
) -> RenderResult:
    start, end = _preview_bounds(song, start_seconds, duration_seconds)
    result = _render_audio(
        song,
        normalize=normalize,
        control=control,
        target_lufs=target_lufs,
        peak_ceiling_dbfs=peak_ceiling_dbfs,
    )
    audio = result.audio[start:end].copy()
    report = {
        **result.report,
        "audio": _metrics(audio, song.sample_rate),
        "preview": {
            "requested_start_seconds": start_seconds,
            "requested_duration_seconds": duration_seconds,
            "start_frame": start,
            "end_frame": end,
            "start_seconds": start / song.sample_rate,
            "duration_seconds": (end - start) / song.sample_rate,
            "context_audio": result.report["audio"],
            "normalization_scope": "full_render",
        },
    }
    control.check()
    return RenderResult(audio, report)


def render_preview_audio(
    song: Song,
    *,
    start_seconds: float,
    duration_seconds: float,
    normalize: bool = True,
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
    target_lufs: float | None = None,
    peak_ceiling_dbfs: float = -1.0,
) -> RenderResult:
    """Crop a full render, preserving seeds, effects, timing, and attenuation.

    End is exclusive and clamped to rendered duration including tails. Boundaries
    use round(seconds * sample_rate). This costs a full render and retains its
    300-second limit. No boundary fades are applied; a cut can click in playback.
    """
    song = Song.model_validate(song.model_dump())
    return _preview_result(
        song,
        start_seconds,
        duration_seconds,
        normalize,
        _RenderControl(progress, cancel),
        target_lufs,
        peak_ceiling_dbfs,
    )


def render_preview(
    song: Song,
    path: str | Path,
    *,
    start_seconds: float,
    duration_seconds: float,
    normalize: bool = True,
    wav_format: WavFormat = "pcm16",
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
    target_lufs: float | None = None,
    peak_ceiling_dbfs: float = -1.0,
) -> dict:
    """Write a context-preserving excerpt; see render_preview_audio for cost/bounds."""
    song = Song.model_validate(song.model_dump())
    _validate_wav_format(wav_format)
    destination = Path(path)
    check_paths([destination])
    control = _RenderControl(progress, cancel)
    result = _preview_result(
        song, start_seconds, duration_seconds, normalize, control, target_lufs, peak_ceiling_dbfs
    )
    report = {**result.report, "output": str(destination), "stems": []}
    _format_report(report, wav_format)
    with _staged_outputs([destination]) as staged:
        control.notify("export", 0, 1)
        _write_wav(staged[0], result.audio, song.sample_rate, wav_format)
        report["wav"] = analyze_wav(staged[0])
        control.notify("export", 1, 1)
    return report
