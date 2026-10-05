"""Causal filters, modulation and generated dance-music processing."""

from __future__ import annotations

import math

import numpy as np

from ._audio import Audio
from ._electronic_dsp import decimate, interpolate
from .model import Chorus, Distortion, Ducker, Filter, Phaser, Song, Tremolo


def processing_tail(effect: Filter | Chorus | Phaser | Distortion | Tremolo | Ducker) -> float:
    if isinstance(effect, Chorus):
        return (effect.delay_ms + effect.depth_ms) / 1000 + 1 / 22050
    if isinstance(effect, Filter):
        cutoff = min(effect.cutoff_hz, effect.end_cutoff_hz or effect.cutoff_hz)
        # Conservative residual decay window, including high-Q low-frequency ringing.
        return max(0.02, 12 * (0.5 + 7.5 * effect.resonance) / (np.pi * cutoff))
    if isinstance(effect, Phaser):
        return 0.1
    if isinstance(effect, Distortion):
        return 64 / 22050
    return 0.0


def _filter(audio: Audio, rate: int, effect: Filter) -> Audio:
    """Trapezoidal state-variable integration, double precision internal states.

    Equations: Andrew Simper, Cytomic, SvfLinearTrapOptimised2 (2013/2016).
    Cutoff sweeps logarithmically in Hz and clamps below the rendering Nyquist.
    """
    out = np.empty_like(audio)
    q = 0.5 + 7.5 * effect.resonance
    k = 1 / q
    ratio = math.log((effect.end_cutoff_hz or effect.cutoff_hz) / effect.cutoff_hz)
    state = [[0.0, 0.0], [0.0, 0.0]]
    for start in range(0, len(audio), 65536):
        stop = min(len(audio), start + 65536)
        fraction = np.minimum(1, np.arange(start, stop) / (rate * effect.sweep_seconds))
        cutoff = np.minimum(rate * 0.44, effect.cutoff_hz * np.exp(ratio * fraction))
        g = np.tan(np.pi * cutoff / rate)
        a1 = 1 / (1 + g * (g + k))
        a2, a3 = g * a1, g * g * a1
        coefficients = list(zip(a1.tolist(), a2.tolist(), a3.tolist(), strict=True))
        for channel in (0, 1):
            s1, s2 = state[channel]
            result = []
            for sample, (c1, c2, c3) in zip(
                audio[start:stop, channel].tolist(), coefficients, strict=True
            ):
                v3 = sample - s2
                v1 = c1 * s1 + c2 * v3
                v2 = s2 + c2 * s1 + c3 * v3
                s1, s2 = 2 * v1 - s1, 2 * v2 - s2
                value = v2 if effect.mode == "lowpass" else sample - k * v1 - v2
                result.append(k * v1 if effect.mode == "bandpass" else value)
            out[start:stop, channel] = result
            state[channel] = [s1, s2]
    return out


def _phaser(audio: Audio, rate: int, effect: Phaser) -> Audio:
    wet = audio.astype(np.float64)
    for stage in range(4):
        for channel in (0, 1):
            previous_in, previous_out = 0.0, 0.0
            for start in range(0, len(audio), 65536):
                stop = min(len(audio), start + 65536)
                time = np.arange(start, stop) / rate
                frequency = (250 * 1.65**stage) * 2 ** (
                    2
                    * effect.depth
                    * np.sin(2 * np.pi * effect.rate_hz * time + channel * np.pi / 2)
                )
                tangent = np.tan(np.pi * np.minimum(frequency, rate * 0.44) / rate)
                coefficients = ((tangent - 1) / (tangent + 1)).tolist()
                result = []
                for sample, a in zip(wet[start:stop, channel].tolist(), coefficients, strict=True):
                    value = a * sample + previous_in - a * previous_out
                    previous_in, previous_out = sample, value
                    result.append(value)
                wet[start:stop, channel] = result
    return wet.astype(np.float32)


def _beat_clock(song: Song | None, start: int, stop: int, rate: int) -> np.ndarray:
    if song is None:
        raise ValueError("tempo-synced effects require the Song timing context")
    beats = np.unique([0.0, song.beats, *(c.beat for c in song.tempo_map)])
    times = np.array([song.beat_to_seconds(float(b)) for b in beats])
    clock = np.arange(start, stop) / rate
    values = np.interp(clock, times, beats)
    last_bpm = song.tempo_map[-1].bpm if song.tempo_map else song.bpm
    beyond = clock > times[-1]
    values[beyond] = song.beats + (clock[beyond] - times[-1]) * last_bpm / 60
    return values


def process(audio: Audio, effect, rate: int, song: Song | None) -> Audio:
    if isinstance(effect, Filter):
        return _filter(audio, rate, effect)
    if isinstance(effect, Phaser):
        return _phaser(audio, rate, effect)
    wet = np.empty_like(audio)
    if isinstance(effect, Ducker):
        if song is None:
            raise ValueError("beat-triggered ducking requires the Song timing context")
        triggers = np.array([song.beat_to_seconds(b) for b in effect.trigger_beats])
        # Each trigger smoothly starts its own dip; overlapping dips take the
        # deeper envelope rather than resetting an earlier recovery upward.
        wet[:] = audio
        depth = np.zeros(len(audio), dtype=np.float64)
        for trigger in triggers:
            start = round(trigger * rate)
            stop = min(
                len(audio),
                start + math.ceil((effect.attack_seconds + effect.release_seconds) * rate),
            )
            age = np.arange(stop - start) / rate
            attack = np.minimum(1, age / effect.attack_seconds)
            recovery = np.clip((age - effect.attack_seconds) / effect.release_seconds, 0, 1)
            dip = np.sin(np.pi * attack / 2) ** 2 * np.cos(np.pi * recovery / 2) ** 2
            depth[start:stop] = np.maximum(depth[start:stop], dip)
        wet *= (1 - effect.depth * depth[:, None]).astype(np.float32)
        return wet
    for start in range(0, len(audio), 65536):
        stop = min(len(audio), start + 65536)
        positions = np.arange(start, stop)
        if isinstance(effect, Chorus):
            for channel in (0, 1):
                delay = effect.delay_ms + effect.depth_ms * np.sin(
                    2 * np.pi * effect.rate_hz * positions / rate + channel * np.pi / 2
                )
                source = positions - delay * rate / 1000
                lower = np.floor(source).astype(int)
                fraction = source - lower
                # Virtual silence outside the padded input, without negative-index wrap.
                lo = np.clip(lower, 0, max(0, len(audio) - 1))
                hi = np.clip(lower + 1, 0, max(0, len(audio) - 1))
                a = audio[lo, channel] * ((lower >= 0) & (lower < len(audio)))
                b = audio[hi, channel] * ((lower + 1 >= 0) & (lower + 1 < len(audio)))
                wet[start:stop, channel] = a * (1 - fraction) + b * fraction
        elif isinstance(effect, Distortion):
            # Overlap supplies the FIR support across processing chunks. It avoids
            # resetting the antialias filter at every 65536-frame boundary.
            # Two 32-frame FIR supports (interpolation then decimation).
            lo, hi = max(0, start - 64), min(len(audio), stop + 64)
            for channel in (0, 1):
                source = audio[lo:hi, channel]
                high = interpolate(source)
                value = decimate(np.tanh(effect.drive * high) / np.tanh(effect.drive))
                wet[start:stop, channel] = value[start - lo : stop - lo]
        elif isinstance(effect, Tremolo):
            phase = _beat_clock(song, start, stop, rate) / effect.period_beats
            wave = 0.5 + 0.5 * np.cos(2 * np.pi * phase)
            if effect.shape == "gate":
                wave = 0.5 + 0.5 * np.tanh(8 * np.cos(2 * np.pi * phase))
            wet[start:stop] = audio[start:stop] * (1 - effect.depth * (1 - wave[:, None]))
        else:
            raise TypeError(f"unsupported effect: {type(effect).__name__}")
    return wet
