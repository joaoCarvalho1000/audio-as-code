"""Generated instrument prototypes: modal strings, resonators and source/filter tones.

No measured spectra or recordings are used. Coefficients are hand-designed;
bowed and wind voices approximate the resulting spectrum, not a coupled
nonlinear bow/reed/lip simulation. See docs/orchestra.md for model boundaries.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from ._orchestra_profiles import HELD, HELD_RELEASE, RESONATORS, STRINGS
from ._orchestra_profiles import HeldProfile as HeldProfile
from ._orchestra_profiles import ResonatorProfile as ResonatorProfile
from ._orchestra_profiles import StringProfile as StringProfile
from .acoustics import (
    colored_noise,
    modulate_noise,
    nyquist_gain,
    resonant_body,
    slow_variation,
    struck_mode,
)
from .instruments import require_instrument
from .model import Tone

Signal = NDArray[np.float64]


EXTRA_INSTRUMENTS = (
    frozenset(STRINGS)
    | frozenset(HELD)
    | frozenset(RESONATORS)
    | {"piano", "cymbal", "tambourine", "synthesizer"}
)


def _formant(frequency: float, formants: tuple) -> float:
    return 1 + sum(
        gain * math.exp(-0.5 * ((frequency - center) / width) ** 2)
        for center, width, gain in formants
    )


def _plucked(
    instrument: str,
    frequency: float,
    t: Signal,
    rate: int,
    brightness: float,
    decay: float,
    position: float | None,
    seed: int,
) -> Signal:
    profile = STRINGS[instrument]
    position = profile.position if position is None else position
    rng = np.random.Generator(np.random.PCG64(seed))
    position = float(np.clip(position + rng.uniform(-0.004, 0.004), 0.05, 0.45))
    polarization_cents = profile.detune or 0.8
    signal = np.zeros(len(t))
    total = 0.0
    for n in range(1, 49):
        f = frequency * n * math.sqrt((1 + profile.stiffness * n * n) / (1 + profile.stiffness))
        # Initial string displacement and observation position select modes.
        amplitude = math.sin(math.pi * n * position) / n**profile.tilt
        amplitude *= math.exp(-(n - 1) / (3 + 25 * brightness))
        amplitude *= rng.uniform(0.97, 1.03)
        if profile.pickup is not None:
            amplitude *= math.sin(math.pi * n * profile.pickup)
        if instrument == "bass_guitar" and n == 1:
            amplitude *= 1.6
        total += abs(amplitude)
        if f >= rate * 0.49:
            continue
        damping = 1 + profile.damping * (n - 1) ** 0.85
        envelope = np.exp(-math.log(1000) * t * damping / decay)
        partial = 0.82 * envelope * np.sin(2 * np.pi * f * t) * nyquist_gain(f, rate)
        companion = f * 2 ** (polarization_cents / 1200)
        partial += (
            0.18
            * np.exp(-math.log(1000) * t * damping / (decay * 1.35))
            * np.sin(2 * np.pi * companion * t)
            * nyquist_gain(companion, rate)
        )
        signal += amplitude * partial
    if total:
        signal *= 0.85 / total
    contact = 0.012 if instrument == "harpsichord" else 0.009
    signal += (
        contact
        * brightness
        * colored_noise(len(t), rate, seed + 1, 1400, 8000)
        * np.exp(-t / 0.006)
    )
    modes = tuple((f, min(0.3, lifetime * 6.9), gain) for f, gain, lifetime in profile.body)
    return resonant_body(signal, rate, modes, wet=0.22)


def _piano_poles(
    frequency: float, damping: float, detunes: tuple[float, ...]
) -> tuple[NDArray[np.complex128], NDArray[np.complex128]]:
    """Passive narrow-band unisons coupled through a resistive bridge.

    The Hermitian part is negative definite: intrinsic string loss plus a
    positive rank-one bridge loss. Common motion radiates more strongly than
    differential motion. Small mistuning transfers energy between the two.
    """
    count = len(detunes)
    frequencies = frequency * 2 ** (np.asarray(detunes) / 1200)
    matrix = np.diag(-0.28 * damping + 2j * np.pi * frequencies)
    matrix -= 0.72 * damping * np.ones((count, count)) / count
    poles, modes = np.linalg.eig(matrix)
    residues = np.sum(modes, axis=0) * np.linalg.solve(modes, np.ones(count)) / count
    return poles, residues


def _forced_piano_pole(t: Signal, pole: complex, contact: float) -> NDArray[np.complex128]:
    """Complex modal response to the same finite hammer pulse as struck_mode.

    Coupled modes have complex residues, so both response quadratures matter.
    Evaluate the three forcing terms only during contact; the tail is one exp.
    """
    attack_frames = int(np.searchsorted(t, contact))
    u = t[:attack_frames]
    response = np.empty(len(t), dtype=np.complex128)
    response[:attack_frames] = 0
    released = 0j
    for weight, offset in ((1, 0), (-0.5, 2 * np.pi / contact), (-0.5, -2 * np.pi / contact)):
        denominator = pole - 1j * offset
        response[:attack_frames] += (
            weight * np.exp(1j * offset * u) * np.expm1(denominator * u) / denominator
        )
        released += (
            weight * np.exp(1j * offset * contact) * np.expm1(denominator * contact) / denominator
        )
    # Reuse the complex output buffer for the long free tail. Keep each
    # operation (and its rounding) in the same order as the analytic expression.
    tail = response[attack_frames:]
    np.multiply(pole, t[attack_frames:] - contact, out=tail)
    np.exp(tail, out=tail)
    np.multiply(released, tail, out=tail)
    response /= contact
    return response


def _piano(
    frequency: float, t: Signal, rate: int, brightness: float, decay: float, seed: int
) -> Signal:
    signal = np.zeros(len(t))
    rng = np.random.Generator(np.random.PCG64(seed))
    stiffness = 0.00009 * (1 + (frequency / 500) ** 1.6)
    # Tight unisons avoid mistaking a beating side-lobe for a shifted fundamental.
    # Upper partials still beat faster because their separation scales with pitch.
    detunes = (0,) if frequency < 65 else (-0.6, 0.6) if frequency < 130 else (-0.9, 0, 0.9)
    contact = min(0.65 / frequency, (0.004 - brightness * 0.0028) * (220 / frequency) ** 0.35)
    total = 0.0
    for n in range(1, 41):
        f = frequency * n * math.sqrt((1 + stiffness * n * n) / (1 + stiffness))
        # Hammer location selects modes; finite forcing supplies contact filtering.
        amplitude = abs(math.sin(math.pi * n * 0.137)) / n**1.1
        amplitude *= math.exp(-((n / (3.5 + brightness * 15)) ** 2))
        amplitude *= rng.uniform(0.98, 1.02)
        total += amplitude
        damping = (1 + 0.16 * n**1.25) * (frequency / 220) ** 0.2
        if len(detunes) == 1:
            # Preserve the single bass string's existing two-polarization decay.
            # There is no neighbouring unison to exchange energy with here.
            if f < rate * 0.49:
                response = 0.8 * struck_mode(t, f, 6.9 * damping / decay, contact)
                response += 0.2 * struck_mode(t, f, 6.9 * damping / (decay * 2.2), contact)
                signal += amplitude * response * nyquist_gain(f, rate)
            continue
        poles, residues = _piano_poles(f, 6.9 * damping / decay, detunes)
        for pole, residue in zip(poles, residues, strict=True):
            partial_frequency = pole.imag / (2 * np.pi)
            if partial_frequency >= rate * 0.49:
                continue
            forced = _forced_piano_pole(t, pole, contact)
            np.multiply(residue, forced, out=forced)
            response = forced.imag
            signal += amplitude * response * nyquist_gain(partial_frequency, rate)
    if total:
        signal *= 0.9 / total
    signal += (
        (0.012 + 0.032 * brightness**2)
        * colored_noise(len(t), rate, seed, 700, 7500)
        * np.exp(-t / 0.009)
    )
    return resonant_body(
        signal,
        rate,
        ((95, 0.2, 0.4), (210, 0.14, 0.3), (580, 0.09, 0.2), (1250, 0.06, 0.1)),
        wet=0.17,
    )


def _bowed_transfer(frequency: float, formants: tuple) -> complex:
    """Designed damped body resonances, including their phase response.

    Each bandpass has its specified peak gain and half-power bandwidth in Hz.
    This is a steady-state body approximation, not measured violin admittance.
    """
    return 1 + sum(
        gain * (1j * frequency * width) / (center**2 - frequency**2 + 1j * frequency * width)
        for center, width, gain in formants
    )


def _held(
    instrument: str,
    frequency: float,
    t: Signal,
    rate: int,
    seed: int,
    brightness: float,
    settings: dict,
    articulation: str | None = None,
    held_frames: int | None = None,
) -> Signal:
    profile = HELD[instrument]
    bowed = instrument in {"violin", "viola", "cello", "double_bass"}
    brass = instrument in {"trumpet", "trombone", "french_horn", "tuba"}
    acoustic = instrument not in {"organ", "theremin"}
    depth = settings.get("vibrato_depth_cents", 0)
    vibrato_rate = settings.get("vibrato_rate_hz", 5)
    motion = slow_variation(t, seed, 0.7)
    pressure = 1 + (0.025 if acoustic else 0) * motion
    vibrato_phase = 2 * np.pi * vibrato_rate * t + (0.09 if acoustic else 0) * slow_variation(
        t, seed + 1, 0.45
    )
    vibrato = depth * (1 - np.exp(-np.maximum(0, t - 0.07) / 0.24)) * np.sin(vibrato_phase)
    drift = 0.9 * slow_variation(t, seed + 2, 0.4) if acoustic else 0
    settling = (-4 if brass else -1.5) * np.exp(-t / 0.025) if acoustic else 0
    glide = settings.get("glide_semitones", 0) * 100 * np.exp(-t / 0.12)
    frequencies = frequency * 2 ** ((vibrato + glide + drift + settling) / 1200)
    # Trapezoidal phase integration follows the instantaneous pitch without
    # the half-sample frequency error of a right-endpoint sum during glides.
    phase = np.zeros(len(t))
    phase[1:] = 2 * np.pi * np.cumsum((frequencies[:-1] + frequencies[1:]) * 0.5) / rate
    lowest_frequency = float(np.min(frequencies))
    signal = np.zeros(len(t))
    total = 0.0
    partials = list(profile.partials)
    if bowed:
        # Bowed strings need bridge-band energy even in their low registers.
        last = len(partials)
        partials.extend(partials[-1] * (last / n) ** 1.15 for n in range(last + 1, 49))
    bloom_envelope = (
        (0.3 if brass else 0.12 if bowed else 0.08)
        * brightness
        * (1 - np.exp(-t / 0.007))
        * np.exp(-t / 0.1)
    )
    # The pressure exponent is capped at harmonic twelve for every voice.
    upper_evolution = pressure ** (1 + 0.12 * 12) if len(partials) >= 12 else None
    # These source/filter gestures are deliberately independent of pitch and
    # velocity. They change harmonic build-up and noise, not just overall gain.
    soft = articulation == "soft"
    transient = np.exp(-t / (3 * profile.attack)) if articulation else None
    release_age = (
        np.maximum(0, t - held_frames / rate) if articulation and held_frames is not None else None
    )
    for n, base in enumerate(partials, start=1):
        if bowed:
            # A rounded Helmholtz corner limits absolute bandwidth; tying that
            # cutoff only to harmonic number erased body-band energy down low.
            bandwidth = 900 + 6500 * brightness**2
            transfer = _bowed_transfer(frequency * n, profile.formants)
            amplitude = base * math.exp(-frequency * (n - 1) / bandwidth) * abs(transfer)
            body_phase = math.atan2(transfer.imag, transfer.real)
        else:
            amplitude = base * math.exp(-(n - 1) * (1 - brightness) * 0.28)
            amplitude *= _formant(frequency * n, profile.formants)
            body_phase = 0
        # Normalize against the designed spectrum, so removing an inaudible
        # mode cannot cause a gain jump in all remaining modes.
        total += amplitude
        if lowest_frequency * n >= rate * 0.49:
            continue
        # Upper modes build after the fundamental, giving a played onset.
        attack = profile.attack * (1 + 0.035 * (n - 1)) / (0.7 + 0.6 * brightness)
        if articulation:
            attack *= (1.8 if soft else 0.45) * (1 + (0.045 if soft else 0.008) * (n - 1))
        onset = 1 - np.exp(-t / attack)
        bloom = 1 + bloom_envelope * (1 - 1 / n)
        if articulation:
            # Soft attacks delay the upper spectrum; accents briefly emphasize
            # it. The nominal sustained spectrum and oscillator pitch survive.
            color = (1 - 1 / n) * transient
            onset *= np.exp(-1.4 * color) if soft else 1 + 0.7 * color
            if release_age is not None:
                loss = HELD_RELEASE[instrument]
                tau = loss.fundamental / (1 + loss.upper_loss * (n - 1))
                onset *= np.exp(-release_age / tau)
        evolution = pressure ** (1 + 0.12 * n) if n < 12 else upper_evolution
        signal += (
            amplitude
            * onset
            * bloom
            * evolution
            * nyquist_gain(frequencies * n, rate)
            * np.sin(n * phase + body_phase)
        )
    if total:
        signal *= 0.8 / total
    noise_amount = profile.bow_noise + settings.get("breath", 0) * 0.16
    if noise_amount:
        noise = colored_noise(len(t), rate, seed, *profile.noise_band)
        noise_envelope = (1 - np.exp(-t / 0.006)) * (1 + 0.6 * np.exp(-t / 0.06)) * pressure
        if articulation:
            # Keep each instrument's colored, phase-modulated noise source.
            # A soft onset brings it in with the bow/air ramp; an accent has a
            # brief excitation burst. Neither adds an unrelated sampled attack.
            noise_attack = profile.attack * 0.75 if soft else 0.004
            noise_envelope = (1 - np.exp(-t / noise_attack)) * pressure
            noise_envelope *= 1 + (0.1 if soft else 1.1) * transient
            if release_age is not None:
                noise_envelope *= np.exp(-release_age / HELD_RELEASE[instrument].noise)
        if instrument == "organ":
            noise_envelope *= np.exp(-t / 0.08)
        # Bow friction and breath are colored by the evolving excitation,
        # rather than a constant noise layer pasted over a stationary tone.
        textured_noise = modulate_noise(
            noise,
            phase + 0.4 * motion,
            float(np.max(frequencies)) + 2,
            rate,
            0.25 if bowed else 0.12,
        )
        signal += textured_noise * noise_amount * noise_envelope
    # Slight amplitude variation accompanies the played vibrato.
    if depth:
        signal *= 1 - 0.025 * (1 - np.cos(2 * np.pi * vibrato_rate * t))
    return signal


def _resonator(
    instrument: str,
    frequency: float,
    t: Signal,
    rate: int,
    seed: int,
    brightness: float,
    decay: float,
) -> Signal:
    profile = RESONATORS[instrument]
    rng = np.random.Generator(np.random.PCG64(seed))
    frequency = {"toms": 125, "congas": 210, "bongos": 340}.get(instrument, frequency)
    membrane = instrument in {"toms", "congas", "bongos", "timpani"}
    signal = np.zeros(len(t))
    total = 0.0
    contact = (0.004 if membrane else 0.0025) * (1.3 - 0.85 * brightness)
    if not membrane:
        material_contact = {
            "electric_piano": 0.0015,
            "xylophone": 0.0008,
            "vibraphone": 0.0025,
            "glockenspiel": 0.0005,
        }[instrument]
        contact = min(0.65 / frequency, material_contact * (1.3 - 0.85 * brightness))
    for index, (ratio, amplitude, lifetime) in enumerate(
        zip(profile.ratios, profile.amplitudes, profile.lifetimes, strict=True)
    ):
        f = frequency * ratio
        amplitude *= 1 if index == 0 else 0.2 + 1.6 * brightness
        amplitude *= rng.uniform(0.975, 1.025)
        total += amplitude
        instantaneous_frequency = f * (1 + 0.08 * np.exp(-t / 0.025)) if membrane else f
        if f >= rate * 0.49:
            continue
        # Tension relaxes after a membrane strike; analytic integral avoids rate drift.
        phase = (
            2 * np.pi * f * (t + 0.08 * 0.025 * (1 - np.exp(-t / 0.025)))
            if membrane
            else 2 * np.pi * f * t
        )
        envelope = np.exp(-math.log(1000) * t / (decay * lifetime))
        partial = np.sin(phase)
        if not membrane:
            partial = struck_mode(t, f, math.log(1000) / (decay * lifetime), contact)
        if instrument in {"vibraphone", "glockenspiel", "electric_piano"}:
            split = f * (1 + 0.0006 * (index + 1))
            partial = 0.85 * partial + 0.15 * struck_mode(
                t, split, math.log(1000) / (decay * lifetime), contact
            ) * nyquist_gain(split, rate)
        signal += (
            amplitude
            * partial
            * (envelope if membrane else 1)
            * nyquist_gain(instantaneous_frequency, rate)
        )
    if total:
        signal *= 0.85 / total
    if membrane:
        signal *= 1 - np.exp(-t / contact)
    signal += (
        profile.strike
        * (0.3 + brightness)
        * colored_noise(len(t), rate, seed, 500, 7000)
        * np.exp(-t / 0.014)
    )
    if profile.tremolo:
        signal *= 1 - profile.tremolo * (0.5 - 0.5 * np.cos(2 * np.pi * 5.5 * t))
    if membrane:
        # A short generated shell/kettle response, driven by the head motion.
        cavity = {"toms": 95, "congas": 145, "bongos": 260, "timpani": frequency * 0.72}[instrument]
        signal = resonant_body(
            signal, rate, ((cavity, 0.12, 1), (cavity * 2.4, 0.055, 0.3)), wet=0.12
        )
    return signal


def _metal(
    instrument: str, t: Signal, rate: int, seed: int, brightness: float, decay: float
) -> Signal:
    rng = np.random.Generator(np.random.PCG64(seed))
    signal = np.zeros(len(t))
    cymbal = instrument == "cymbal"
    frequencies = np.geomspace(280 if cymbal else 1600, 19000, 192 if cymbal else 48)
    frequencies *= rng.uniform(0.96, 1.04, len(frequencies))
    collisions = [0.0] if cymbal else [0.0, *np.sort(rng.uniform(0.005, 0.085, 5))]
    total = 0.0
    for index, f in enumerate(frequencies):
        if f >= rate * 0.49:
            continue
        amplitude = (f / frequencies[0]) ** (-0.65 + 0.45 * brightness)
        lifetime = decay / (1 + 0.028 * index)
        phase = rng.uniform(-np.pi, np.pi)
        # Each collision is an analytic resonator excitation, not a sampled hit.
        for collision in collisions:
            age = np.maximum(0, t - collision)
            active = t >= collision
            attack = 1 - np.exp(-age / 0.0008)
            signal += (
                amplitude
                * active
                * attack
                * np.sin(2 * np.pi * f * age + phase)
                * np.exp(-6.9 * age / lifetime)
                / len(collisions)
            )
        total += amplitude**2
    if total:
        signal *= (0.23 if cymbal else 0.34) / math.sqrt(total)
    wash = colored_noise(len(t), rate, seed + 1, 2400 if cymbal else 4000, 15000)
    wash *= (1 - np.exp(-t / 0.001)) * np.exp(-6.9 * t / (decay * 0.35))
    return signal + (0.12 if cymbal else 0.025) * wash * (0.4 + brightness)


def _synthesizer(
    frequency: float, t: Signal, rate: int, brightness: float, settings: dict
) -> Signal:
    signal = np.zeros(len(t))
    detune = settings.get("detune_cents", 8)
    total = 0.0
    cutoff = 2 + brightness * (5 + 20 * np.exp(-t / 0.25))
    for n in range(1, 33):
        amplitude = 1 / n
        total += amplitude
        for cents, weight in [(-detune, 0.25), (0, 0.5), (detune, 0.25)]:
            partial_frequency = frequency * n * 2 ** (cents / 1200)
            if partial_frequency >= rate * 0.49:
                continue
            phase = 2 * np.pi * partial_frequency * t
            signal += (
                weight
                * amplitude
                * nyquist_gain(partial_frequency, rate)
                * np.sin(phase)
                / (1 + (n / cutoff) ** 4)
            )
    return signal * (0.9 / total) if total else signal


def synthesize(
    instrument: str,
    frequency: float,
    frames: int,
    rate: int,
    seed: int,
    velocity: float,
    tone: Tone | None,
    articulation: str | None = None,
    held_frames: int | None = None,
) -> Signal:
    info = require_instrument(instrument)
    if instrument not in EXTRA_INSTRUMENTS:
        raise ValueError(f"No orchestra model for {instrument!r}")
    if articulation is not None and articulation not in info.articulations:
        raise ValueError(f"articulation {articulation!r} is not supported by {instrument}")
    if frames < 1 or (info.midi_note is None and frequency >= rate / 2):
        return np.zeros(frames)
    tone = tone or Tone()
    settings = dict(info.default_tone)
    settings.update({key: value for key, value in tone.model_dump().items() if value is not None})
    brightness = min(1.0, settings["brightness"] * 0.75 + velocity * 0.25)
    decay = settings.get("decay_seconds", info.default_decay_seconds)
    t = np.arange(frames, dtype=np.float64) / rate
    if instrument in STRINGS:
        return _plucked(
            instrument, frequency, t, rate, brightness, decay, tone.pluck_position, seed
        )
    if instrument == "piano":
        return _piano(frequency, t, rate, brightness, decay, seed)
    if instrument in HELD:
        return _held(
            instrument, frequency, t, rate, seed, brightness, settings, articulation, held_frames
        )
    if instrument in RESONATORS:
        return _resonator(instrument, frequency, t, rate, seed, brightness, decay)
    if instrument in {"cymbal", "tambourine"}:
        return _metal(instrument, t, rate, seed, brightness, decay)
    return _synthesizer(frequency, t, rate, brightness, settings)
