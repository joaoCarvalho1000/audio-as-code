"""Musical controls, numerical audio quality and additive compatibility contracts."""

import hashlib
import json

import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import Note, Song, Tone, Track, get_instrument, render_audio
from audio_as_code._electronic_dsp import fm_tone, harmonic_oscillator, oscillator_phase
from audio_as_code._voices import _voice
from audio_as_code.acoustics import nyquist_gain
from audio_as_code.electronic import ELECTRONIC_INSTRUMENTS
from audio_as_code.render import _canonical_score


def rms(x):
    return np.sqrt(np.mean(np.square(x.astype(np.float64))))


def centroid(x, rate=22050):
    power = abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    return np.sum(power * np.fft.rfftfreq(len(x), 1 / rate)) / np.sum(power)


@pytest.mark.parametrize("instrument", sorted(ELECTRONIC_INSTRUMENTS))
@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_all_new_voices_have_finite_deterministic_non_silent_audio(instrument, rate):
    info = get_instrument(instrument)
    args = (instrument, info.preview_pitch, rate // 2, rate, 171)
    audio = _voice(*args)
    np.testing.assert_array_equal(audio, _voice(*args))
    np.testing.assert_array_equal(audio, _voice(*args, tone=Tone()))
    assert audio.dtype == np.float32 and audio.shape == (rate // 2,)
    assert np.isfinite(audio).all() and 0.0001 < rms(audio) < 1
    assert np.max(abs(audio)) < 2
    assert audio[0] == audio[-1] == 0
    for frames in (1, 2, 3, 17):
        short = _voice(instrument, info.preview_pitch, frames, rate, 1)
        assert np.isfinite(short).all() and short[0] == short[-1] == 0


@pytest.mark.parametrize("instrument", sorted(ELECTRONIC_INSTRUMENTS))
def test_controls_have_audible_signal_effects_and_are_validated(instrument):
    info = get_instrument(instrument)
    candidates = {
        "brightness": 0.9,
        "decay_seconds": 0.15,
        "pluck_position": 0.4,
        "cutoff_hz": 3200,
        "resonance": 0.9,
        "detune_cents": 35,
        "glide_semitones": -7,
        "glide_seconds": 0.7,
        "filter_env_octaves": 5,
        "filter_decay_seconds": 0.8,
        "fm_index": 8,
        "fm_ratio": 3,
        "modulation_rate_hz": 5,
        "tuning_semitones": 7,
    }
    for control in info.tone_controls:
        # Parameters conditional on a depth need that depth enabled to matter.
        context = {"glide_semitones": -12} if control == "glide_seconds" else {}
        if control == "filter_decay_seconds":
            context = {"filter_env_octaves": 2}
        baseline = Tone(**context)
        changed = Tone(**{**context, control: candidates[control]})
        Track(name="Probe", instrument=instrument, tone=changed)
        args = (instrument, info.preview_pitch, 11025, 22050, 7)
        a, b = _voice(*args, tone=baseline), _voice(*args, tone=changed)
        assert rms(a - b) > 1e-6, (instrument, control)
    unsupported = next(k for k in candidates if k not in info.tone_controls)
    with pytest.raises(ValidationError, match="not supported"):
        Track(
            name="Reject",
            instrument=instrument,
            tone=Tone(**{unsupported: candidates[unsupported]}),
        )


@pytest.mark.parametrize(
    "instrument",
    [
        "acid_bass",
        "supersaw",
        "reese_bass",
        "disco_bass",
        "clavinet",
        "trance_pluck",
        "string_machine",
        "sub_bass",
    ],
)
@pytest.mark.parametrize("pitch", [33, 57, 81])
def test_pitched_fundamentals_stay_in_tune(instrument, pitch):
    rate = 22050
    info = get_instrument(instrument)
    tone = Tone(detune_cents=0) if "detune_cents" in info.tone_controls else None
    audio = _voice(instrument, pitch, rate * 2, rate, 67, tone=tone)[rate // 20 : rate // 2]
    size = len(audio) * 16
    power = abs(np.fft.rfft(audio * np.hanning(len(audio)), n=size))
    expected = 440 * 2 ** ((pitch - 69) / 12)
    low, high = int(expected * 0.97 * size / rate), int(expected * 1.03 * size / rate)
    peak = low + np.argmax(power[low : high + 1])
    a, b, c = np.log(power[peak - 1 : peak + 2] + 1e-30)
    measured = (peak + 0.5 * (a - c) / (a - 2 * b + c)) * rate / size
    assert abs(1200 * np.log2(measured / expected)) < 5


def test_glide_frequency_follows_integrated_phase_and_reaches_destination():
    t = np.arange(22050) / 22050
    phase, frequency = oscillator_phase(t, 110, -12, 0.08)
    measured = np.diff(phase) * 22050 / (2 * np.pi)
    np.testing.assert_allclose(measured, (frequency[:-1] + frequency[1:]) / 2, rtol=1e-7)
    assert frequency[0] == 55 and frequency[-1] == pytest.approx(110, abs=0.001)


def test_fm_matches_independent_high_rate_analytic_reference():
    rate, frequency, index, ratio = 22050, 440, 4.0, 2
    t = np.arange(rate) / rate
    actual = fm_tone(t, frequency, rate, np.full(len(t), index), ratio)
    # The reference evaluates 16x and uses ideal Fourier low-pass filtering,
    # independently of the production FIR decimator. Integer-period test signal.
    high_t = np.arange(rate * 16) / (rate * 16)
    phase = 2 * np.pi * frequency * high_t
    reference = np.sin(phase + index * np.sin(ratio * phase))
    spectrum = np.fft.rfft(reference)
    spectrum[np.fft.rfftfreq(len(reference), 1 / (rate * 16)) > rate * 0.45] = 0
    expected = np.fft.irfft(spectrum, n=len(reference))[::16]
    assert rms(actual[100:-100] - expected[100:-100]) < 0.004


@pytest.mark.parametrize("instrument", sorted(ELECTRONIC_INSTRUMENTS))
def test_extreme_controls_and_registers_are_stable(instrument):
    info = get_instrument(instrument)
    settings = {
        "brightness": 1,
        "decay_seconds": 20,
        "pluck_position": 0.05,
        "cutoff_hz": 20000,
        "resonance": 1,
        "filter_env_octaves": 6,
        "filter_decay_seconds": 0.01,
        "detune_cents": 40,
        "glide_semitones": 24,
        "glide_seconds": 0.005,
        "fm_index": 12,
        "fm_ratio": 8,
        "modulation_rate_hz": 20,
        "tuning_semitones": 24,
    }
    tone = Tone(**{k: v for k, v in settings.items() if k in info.tone_controls})
    for pitch in (0, 60, 127):
        audio = _voice(instrument, pitch, 4000, 22050, 68, tone=tone)
        assert np.isfinite(audio).all() and np.max(abs(audio)) < 4
        assert audio[0] == audio[-1] == 0


def test_acid_accent_and_funk_gestures_change_timbre_not_just_level():
    for instrument, gesture in (
        ("acid_bass", "accented"),
        ("bass_guitar", "slap"),
        ("bass_guitar", "pop"),
        ("electric_guitar", "muted"),
    ):
        pitch = 40 if instrument == "bass_guitar" else 52
        args = (instrument, pitch, 22050, 22050, 8)
        dry, changed = _voice(*args), _voice(*args, articulation=gesture)
        assert abs(centroid(dry[:4000]) - centroid(changed[:4000])) > 5
        if gesture == "muted":
            assert rms(changed[5000:]) < rms(dry[5000:]) * 0.1
    with pytest.raises(ValidationError, match="not supported"):
        Track(name="Bad", instrument="piano", articulation="slap")


def test_new_optional_tone_defaults_preserve_legacy_score_identity():
    song = Song(tracks=[Track(name="Old", instrument="guitar", tone=Tone(), notes=[Note()])])
    data = _canonical_score(song)
    expected = song.model_dump(mode="json")
    for key in ("tempo_map", "effects", "automation"):
        expected.pop(key)
    track = expected["tracks"][0]
    for key in ("articulation", "automation", "effects", "release_seconds", "pedal"):
        track.pop(key)
    for key in ("articulation", "release_seconds"):
        track["notes"][0].pop(key)
    track["tone"] = {
        k: v
        for k, v in track["tone"].items()
        if k
        in {
            "brightness",
            "decay_seconds",
            "pluck_position",
            "breath",
            "vibrato_depth_cents",
            "vibrato_rate_hz",
            "glide_semitones",
            "detune_cents",
        }
    }
    assert data == expected
    digest = hashlib.sha256(
        json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert render_audio(song).report["score_sha256"] == digest


@pytest.mark.parametrize("width", [0.25, 0.5, 0.75])
def test_pulse_phase_matches_a_centered_rectangular_wave(width):
    rate, frequency = 22050, 440
    phase = 2 * np.pi * frequency * np.arange(4000) / rate
    actual = harmonic_oscillator(
        phase,
        np.full(len(phase), frequency),
        rate,
        np.full(len(phase), 1e12),
        pulse_width=width,
    )
    # Fourier-analyze a dense rectangle, rather than copying the oscillator's
    # sine-coefficient expression. Half-cell sampling avoids ambiguous edges.
    size = 65536
    grid = (np.arange(size) + 0.5) / size
    rectangle = ((grid < width / 2) | (grid > 1 - width / 2)).astype(float)
    spectrum = np.fft.rfft(rectangle - np.mean(rectangle)) / size
    expected = np.zeros(len(phase))
    for harmonic in range(1, int(rate * 0.49 / frequency) + 1):
        coefficient = spectrum[harmonic] * np.exp(-1j * np.pi * harmonic / size)
        expected += (
            2
            * (coefficient * np.exp(1j * harmonic * phase)).real
            * nyquist_gain(harmonic * frequency, rate)
        )
    np.testing.assert_allclose(actual, expected * (0.18 * np.pi), atol=1e-7, rtol=0)


@pytest.mark.parametrize("instrument", ["metal_hat", "open_hat", "electronic_ride"])
def test_metallic_tail_loses_upper_energy_faster_than_its_lower_ring(instrument):
    rate = 22050
    audio = _voice(instrument, 60, rate * 2, rate, 15, tone=Tone(decay_seconds=3))
    early = audio[rate // 20 : rate // 4]
    late = audio[rate : rate + rate // 5]
    assert centroid(late, rate) < centroid(early, rate) * 0.9
    assert rms(late) < rms(early)
