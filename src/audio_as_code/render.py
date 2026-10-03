"""Deterministic, in-process synthesis. No audio device, API key, or DAW needed."""

from __future__ import annotations

import hashlib
import json
import math
import wave
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from ._paths import check_paths
from .acoustics import colored_noise, nyquist_gain
from .automation import automation_values
from .effects import apply_effects
from .extended import EXTENDED_INSTRUMENTS
from .extended import synthesize as synthesize_extended
from .instruments import KIT_NOTES, PHYSICAL_INSTRUMENTS
from .model import Song, Tone, Track, midi_pitch
from .orchestra import EXTRA_INSTRUMENTS
from .orchestra import synthesize as synthesize_orchestra
from .physical import synthesize

MAX_RENDER_SECONDS = 300
PEAK_CEILING = 0.95
Audio = NDArray[np.float32]


@dataclass(frozen=True)
class RenderResult:
    audio: Audio
    report: dict


def _voice(
    instrument: str,
    pitch: int,
    frames: int,
    rate: int,
    seed: int,
    velocity: float = 0.8,
    tone: Tone | None = None,
    held_frames: int | None = None,
) -> Audio:
    if instrument == "drum_machine":
        return _voice(
            KIT_NOTES[pitch], pitch, frames, rate, seed, velocity, held_frames=held_frames
        )
    t = np.arange(frames, dtype=np.float64) / rate
    frequency = 440 * 2 ** ((pitch - 69) / 12)
    phase = 2 * np.pi * frequency * t
    if instrument in EXTENDED_INSTRUMENTS:
        signal = synthesize_extended(instrument, frequency, frames, rate, seed, velocity, tone)
    elif instrument in EXTRA_INSTRUMENTS:
        signal = synthesize_orchestra(instrument, frequency, frames, rate, seed, velocity, tone)
    elif instrument in PHYSICAL_INSTRUMENTS:
        signal = synthesize(instrument, frequency, frames, rate, seed, velocity, tone)
    elif instrument == "kick":
        # Analytic integral of an exponential pitch sweep; independent of sample rate.
        sweep = 60 + 60 * velocity
        phase = 2 * np.pi * (48 * t + sweep * (1 - np.exp(-35 * t)) / 35)
        signal = np.sin(phase) * np.exp(-9 * t)
        signal += (
            0.035 * velocity * colored_noise(frames, rate, seed, 1800, 9000) * np.exp(-t / 0.006)
        )
    elif instrument in {"snare", "hat"}:
        if instrument == "snare":
            noise = colored_noise(frames, rate, seed, 1100, 9500)
            body = 0.32 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.045) + 0.14 * np.sin(
                2 * np.pi * 330 * t
            ) * np.exp(-t / 0.028)
            rattle = (
                0.72
                * noise
                * (1 + 0.18 * np.sin(2 * np.pi * 83 * t))
                * np.exp(-t / (0.055 + 0.025 * velocity))
            )
            signal = body + rattle
        else:
            noise = colored_noise(frames, rate, seed, 4500, 16000)
            metal = (
                sum(
                    np.sin(2 * np.pi * f * t) * nyquist_gain(f, rate)
                    for f in (3170, 4211, 5783, 7139, 9323)
                )
                / 5
            )
            signal = (0.65 * noise + 0.12 * metal) * np.exp(-t / (0.018 + 0.01 * velocity))
    else:
        # Finite harmonic sums avoid the unbounded harmonics of naive square/saw waves.
        harmonics = {
            "sine": [(1, 1)],
            "triangle": [(n, (-1) ** ((n - 1) // 2) / n**2) for n in range(1, 16, 2)],
            "pluck": [(n, 1 / n**1.6) for n in range(1, 9)],
            "bass": [(1, 1), (2, 0.35), (3, 0.12)],
            "pad": [(1, 1), (2, 0.25), (3, 0.12), (4, 0.06)],
        }[instrument]
        signal = np.zeros(frames)
        weight = 0.0
        for harmonic, amplitude in harmonics:
            if frequency * harmonic >= rate / 2:
                continue
            partial = np.sin(phase * harmonic) * amplitude
            if instrument == "pluck":
                partial *= np.exp(-t * (2.5 + harmonic * 0.8))
            signal += partial
            weight += abs(amplitude)
        if weight:
            signal /= weight
        if instrument == "bass":
            signal *= 0.65 + 0.35 * np.exp(-6 * t)

    # Every voice begins and ends at zero. Envelope fits even very short notes.
    attack_seconds = {
        "pad": 0.08,
        "guitar": 0.001,
        "marimba": 0.0005,
        "piano": 0.0005,
        "xylophone": 0.0005,
        "glockenspiel": 0.0005,
        "mandolin": 0.001,
        "kalimba": 0.0005,
        "celesta": 0.0005,
        "recorder": 0.003,
    }.get(instrument, 0.003)
    release_seconds = {
        "pad": 0.15,
        "guitar": 0.065,
        "electric_guitar": 0.055,
        "bass_guitar": 0.07,
        "harp": 0.12,
        "ukulele": 0.045,
        "banjo": 0.035,
        "harpsichord": 0.04,
        "piano": 0.12,
        "electric_piano": 0.09,
        "marimba": 0.055,
        "bell": 0.12,
        "xylophone": 0.035,
        "vibraphone": 0.12,
        "glockenspiel": 0.1,
        "violin": 0.09,
        "viola": 0.11,
        "cello": 0.13,
        "double_bass": 0.16,
        "flute": 0.08,
        "clarinet": 0.055,
        "saxophone": 0.075,
        "oboe": 0.065,
        "bassoon": 0.08,
        "trumpet": 0.055,
        "trombone": 0.075,
        "french_horn": 0.1,
        "tuba": 0.13,
        "organ": 0.06,
        "theremin": 0.1,
        "timpani": 0.12,
        "cymbal": 0.1,
        "tambourine": 0.045,
        "mandolin": 0.06,
        "kalimba": 0.08,
        "celesta": 0.1,
        "recorder": 0.055,
    }.get(instrument, 0.02)
    attack = min(max(1, round(attack_seconds * rate)), max(1, (held_frames or frames) // 3))
    release = (
        frames - held_frames
        if held_frames is not None
        else min(max(1, round(release_seconds * rate)), max(1, frames // 3))
    )
    signal[:attack] *= np.linspace(0, 1, attack)
    release_curve = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, release)) if release > 1 else 0
    signal[-release:] *= release_curve
    return signal.astype(np.float32)


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
    samples_per_beat = song.sample_rate * 60 / song.bpm
    angle = (track.pan + 1) * np.pi / 4
    left, right = math.cos(angle), math.sin(angle)
    for index, note in enumerate(track.notes):
        start = round(note.start * samples_per_beat)
        end = min(frames, round((note.start + note.duration) * samples_per_beat))
        if end <= start or track.gain == 0:
            continue
        # Track-local seed keeps noise unchanged when an unrelated track is added.
        seed_data = f"{song.seed}:{track.name}:{index}".encode()
        seed = int.from_bytes(hashlib.sha256(seed_data).digest()[:8], "little")
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


def _note_frame(song: Song, beat: float) -> int:
    # Retain the original arithmetic order for legacy timing on rounding boundaries.
    if not song.tempo_map:
        return round(beat * (song.sample_rate * 60 / song.bpm))
    return round(song.beat_to_seconds(beat) * song.sample_rate)


def _expressive_track_audio(song: Song, track: Track, frames: int) -> Audio:
    mono = np.zeros(frames, dtype=np.float32)
    for index, note in enumerate(track.notes):
        start = _note_frame(song, note.start)
        held_end = _note_frame(song, song.note_gate_end(track, note))
        release = song.note_release_seconds(track, note)
        end = min(frames, held_end + round(release * song.sample_rate))
        if held_end <= start:
            continue
        seed_data = f"{song.seed}:{track.name}:{index}".encode()
        seed = int.from_bytes(hashlib.sha256(seed_data).digest()[:8], "little")
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


def _metrics(audio: Audio, rate: int) -> dict:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) if audio.size else 0.0
    return {
        "sample_rate": rate,
        "channels": audio.shape[1],
        "frames": len(audio),
        "duration_seconds": len(audio) / rate,
        "peak": peak,
        "rms": rms,
        "peak_dbfs": 20 * math.log10(peak) if peak > 0 else None,
        "rms_dbfs": 20 * math.log10(rms) if rms > 0 else None,
        "clipped_samples": int(np.count_nonzero(np.abs(audio) >= 1)),
        "silent": peak == 0,
    }


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


def _write_wav(path: Path, audio: Audio, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.rint(audio * 32768), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(pcm.tobytes())


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


def analyze_wav(path: str | Path) -> dict:
    """Measure a 16-bit PCM WAV in blocks. These are signal checks, not music criticism."""
    peak = 0
    squares = 0.0
    count = 0
    clipped = 0
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2 or stream.getcomptype() != "NONE":
            raise ValueError("analysis supports uncompressed 16-bit PCM WAV files")
        channels, rate, frames = stream.getnchannels(), stream.getframerate(), stream.getnframes()
        if rate <= 0:
            raise ValueError("WAV sample rate must be positive")
        while data := stream.readframes(65536):
            if len(data) % (2 * channels):
                raise ValueError("WAV is truncated or malformed: incomplete PCM frame")
            pcm = np.frombuffer(data, dtype="<i2").astype(np.float64)
            count += pcm.size
            peak = max(peak, float(np.max(np.abs(pcm))))
            squares += float(np.sum(pcm * pcm))
            clipped += int(np.count_nonzero((pcm >= 32767) | (pcm <= -32768)))
    if count != frames * channels:
        raise ValueError("WAV is truncated: actual samples do not match the file header")
    rms = math.sqrt(squares / count) / 32768 if count else 0.0
    amplitude = peak / 32768
    return {
        "sample_rate": rate,
        "channels": channels,
        "frames": frames,
        "duration_seconds": frames / rate,
        "peak": amplitude,
        "rms": rms,
        "peak_dbfs": 20 * math.log10(amplitude) if amplitude else None,
        "rms_dbfs": 20 * math.log10(rms) if rms else None,
        "full_scale_samples": clipped,
        "silent": peak == 0,
    }
