"""Numerical DSP checks, not a perceptual-realism or musical-quality evaluation."""

import itertools

import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import Note, Song, Tone, Track, export_midi, get_instrument, render_audio
from audio_as_code.extended import EXTENDED_INSTRUMENTS, synthesize
from audio_as_code.render import _voice


def _frequency(pitch):
    return 440 * 2 ** ((pitch - 69) / 12)


def _raw(instrument, *, pitch=69, seconds=1, rate=22050, seed=9, velocity=0.8, tone=None):
    return synthesize(
        instrument, _frequency(pitch), round(seconds * rate), rate, seed, velocity, tone
    )


def _peak_frequency(audio, rate, expected, fractional_window=0.03):
    size = len(audio) * 8
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio)), n=size))
    lo = round(expected * (1 - fractional_window) * size / rate)
    hi = round(expected * (1 + fractional_window) * size / rate)
    index = lo + np.argmax(spectrum[lo : hi + 1])
    a, b, c = np.log(spectrum[index - 1 : index + 2] + 1e-30)
    correction = 0.5 * (a - c) / (a - 2 * b + c)
    return (index + correction) * rate / size


@pytest.mark.parametrize("instrument", sorted(EXTENDED_INSTRUMENTS))
def test_distinct_implemented_voices_are_registered_and_repeatable(instrument):
    info = get_instrument(instrument)
    assert info.status == "available"
    audio = _raw(instrument, pitch=info.preview_pitch)
    assert audio.dtype == np.float64
    assert np.isfinite(audio).all()
    assert 0.01 < np.max(np.abs(audio)) < 1
    np.testing.assert_array_equal(audio, _raw(instrument, pitch=info.preview_pitch))
    assert not np.array_equal(audio, _raw(instrument, pitch=info.preview_pitch, seed=10))


@pytest.mark.parametrize("instrument", sorted(EXTENDED_INSTRUMENTS))
@pytest.mark.parametrize("rate", [22050, 44100, 48000])
@pytest.mark.parametrize("upper", [False, True])
def test_extreme_pitch_and_supported_controls_remain_finite_and_bounded(instrument, rate, upper):
    limits = (
        {
            "brightness": 1,
            "decay_seconds": 20,
            "pluck_position": 0.05,
            "detune_cents": 40,
            "breath": 1,
            "vibrato_depth_cents": 100,
            "vibrato_rate_hz": 12,
        }
        if upper
        else {
            "brightness": 0,
            "decay_seconds": 0.1,
            "pluck_position": 0.45,
            "detune_cents": 0,
            "breath": 0,
            "vibrato_depth_cents": 0,
            "vibrato_rate_hz": 0.1,
        }
    )
    info = get_instrument(instrument)
    tone = Tone(**{key: value for key, value in limits.items() if key in info.tone_controls})
    for pitch in (0, 48, info.preview_pitch, 96, 127):
        audio = _raw(instrument, pitch=pitch, seconds=0.12, rate=rate, tone=tone)
        assert np.isfinite(audio).all()
        assert np.max(np.abs(audio)) < 1.1
        if _frequency(pitch) >= rate / 2:
            assert not np.any(audio)


@pytest.mark.parametrize("instrument", sorted(EXTENDED_INSTRUMENTS))
@pytest.mark.parametrize("frames", [0, 1, 2, 3, 31])
def test_short_buffers_have_the_requested_shape(instrument, frames):
    audio = synthesize(instrument, 440, frames, 22050, 3, 0.8, None)
    assert audio.shape == (frames,)
    assert audio.dtype == np.float64
    assert np.isfinite(audio).all()


@pytest.mark.parametrize(
    "instrument,pitches",
    [
        ("mandolin", (55, 67, 88)),
        ("kalimba", (60, 72, 84)),
        ("celesta", (60, 79, 96)),
        ("recorder", (72, 84, 96)),
    ],
)
def test_fundamentals_track_written_pitch_through_intended_register(instrument, pitches):
    rate = 22050
    for pitch in pitches:
        audio = _raw(instrument, pitch=pitch, seconds=1.6, rate=rate)[rate // 20 : rate]
        measured = _peak_frequency(audio, rate, _frequency(pitch))
        cents = 1200 * np.log2(measured / _frequency(pitch))
        assert abs(cents) < 5, (instrument, pitch, cents)


@pytest.mark.parametrize("instrument", ["mandolin", "kalimba", "celesta"])
def test_decay_control_increases_late_energy(instrument):
    short = _raw(instrument, seconds=2, tone=Tone(decay_seconds=0.3))
    long = _raw(instrument, seconds=2, tone=Tone(decay_seconds=5))
    assert np.mean(long[22050:] ** 2) > 100 * np.mean(short[22050:] ** 2)


@pytest.mark.parametrize("instrument", sorted(EXTENDED_INSTRUMENTS))
def test_brightness_and_velocity_change_normalized_timbre(instrument):
    # Normalize away level so this tests excitation/timbre, not a gain multiplier.
    versions = [
        _raw(instrument, seconds=0.2, tone=Tone(brightness=brightness), velocity=velocity)
        for brightness, velocity in ((0.05, 0.8), (0.95, 0.8), (0.5, 0.2), (0.5, 1.0))
    ]
    spectra = [np.abs(np.fft.rfft(audio * np.hanning(len(audio)))) for audio in versions]
    spectra = [s / np.linalg.norm(s) for s in spectra]
    assert np.linalg.norm(spectra[0] - spectra[1]) > 0.015
    assert np.linalg.norm(spectra[2] - spectra[3]) > 0.005


def test_mandolin_pair_detune_preserves_center_and_pluck_changes_spectrum():
    rate = 22050
    paired = _raw("mandolin", seconds=3, tone=Tone(decay_seconds=20, detune_cents=40))
    expected = 440
    lower = _peak_frequency(paired, rate, expected * 2 ** (-20 / 1200), 0.004)
    upper = _peak_frequency(paired, rate, expected * 2 ** (20 / 1200), 0.004)
    assert abs(1200 * np.log2(np.sqrt(lower * upper) / expected)) < 1
    assert 38 < 1200 * np.log2(upper / lower) < 42
    middle = _raw("mandolin", tone=Tone(pluck_position=0.40))
    bridge = _raw("mandolin", tone=Tone(pluck_position=0.06))
    assert np.linalg.norm(middle - bridge) / np.linalg.norm(middle) > 0.15


def test_recorder_breath_and_vibrato_change_sustained_signal():
    dry = _raw("recorder", seconds=2, tone=Tone(breath=0, vibrato_depth_cents=0))
    airy = _raw("recorder", seconds=2, tone=Tone(breath=1, vibrato_depth_cents=0))
    vibrato = _raw(
        "recorder", seconds=2, tone=Tone(breath=0, vibrato_depth_cents=35, vibrato_rate_hz=5)
    )
    faster = _raw(
        "recorder", seconds=2, tone=Tone(breath=0, vibrato_depth_cents=35, vibrato_rate_hz=8)
    )
    assert np.mean(dry[33075:] ** 2) > 0.8 * np.mean(dry[11025:22050] ** 2)
    assert np.sqrt(np.mean((airy - dry) ** 2)) > 0.001
    assert np.sqrt(np.mean((vibrato - dry) ** 2)) > 0.05
    assert np.sqrt(np.mean((faster - vibrato) ** 2)) > 0.05


def test_new_models_have_distinct_spectral_shapes():
    spectra = {}
    for instrument in sorted(EXTENDED_INSTRUMENTS):
        audio = _raw(instrument, seconds=0.25, tone=Tone(brightness=0.8))
        spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
        spectra[instrument] = spectrum / np.linalg.norm(spectrum)
    for first, second in itertools.combinations(spectra, 2):
        assert np.linalg.norm(spectra[first] - spectra[second]) > 0.08, (first, second)


@pytest.mark.parametrize("instrument,ratio", [("kalimba", 6.267), ("celesta", 2.7565)])
def test_lamella_and_bar_have_their_respective_inharmonic_modes(instrument, ratio):
    rate = 22050
    audio = _raw(instrument, pitch=57, seconds=0.2, tone=Tone(brightness=1, decay_seconds=5))
    expected = 220 * ratio
    measured = _peak_frequency(audio, rate, expected)
    assert abs(measured - expected) < 1
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
    bins = np.fft.rfftfreq(len(audio), 1 / rate)
    mode = np.max(spectrum[np.abs(bins - expected) < 15])
    background = np.max(spectrum[(np.abs(bins - expected) > 40) & (np.abs(bins - expected) < 80)])
    assert mode > 20 * background


@pytest.mark.parametrize("instrument", sorted(EXTENDED_INSTRUMENTS))
def test_upper_modes_do_not_fold_into_audio_band(instrument):
    rate = 22050
    tone = (
        Tone(breath=0, vibrato_depth_cents=0) if instrument == "recorder" else Tone(decay_seconds=5)
    )
    audio = synthesize(instrument, rate * 0.2, rate, rate, 3, 0.8, tone)[rate // 2 :]
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio)))) ** 2
    bins = np.fft.rfftfreq(len(audio), 1 / rate)
    allowed = (np.abs(bins - rate * 0.2) < 35) | (np.abs(bins - rate * 0.4) < 70)
    assert np.sum(spectrum[~allowed]) < 0.001 * np.sum(spectrum)


def test_recorder_and_celesta_are_not_existing_flute_and_glockenspiel_profiles():
    for first, second in [("recorder", "flute"), ("celesta", "glockenspiel")]:
        versions = [_voice(instrument, 72, 11025, 22050, 3) for instrument in (first, second)]
        spectra = [np.abs(np.fft.rfft(a * np.hanning(len(a)))) for a in versions]
        spectra = [s / np.linalg.norm(s) for s in spectra]
        assert np.linalg.norm(spectra[0] - spectra[1]) > 0.08


@pytest.mark.parametrize(
    "instrument,unsupported",
    [
        ("mandolin", "breath"),
        ("kalimba", "pluck_position"),
        ("celesta", "detune_cents"),
        ("recorder", "decay_seconds"),
    ],
)
def test_only_implemented_controls_validate(instrument, unsupported):
    with pytest.raises(ValidationError, match="not supported"):
        Track(name="Invalid", instrument=instrument, tone=Tone(**{unsupported: 0.2}))
    with pytest.raises(ValueError, match="No extended model"):
        synthesize("sine", 440, 32, 22050, 0, 0.8, None)


@pytest.mark.parametrize(
    "instrument,program",
    [
        ("mandolin", 25),
        ("kalimba", 108),
        ("celesta", 8),
        ("recorder", 74),
    ],
)
def test_score_render_gates_and_midi_programs(instrument, program, tmp_path):
    import mido

    info = get_instrument(instrument)
    voice = _voice(instrument, info.preview_pitch, 22050, 22050, 91)
    assert voice[0] == voice[-1] == 0
    song = Song(
        beats=1,
        sample_rate=22050,
        tracks=[
            Track(
                name=instrument,
                instrument=instrument,
                notes=[Note(pitch=info.preview_pitch)],
            )
        ],
    )
    report = render_audio(song).report
    assert not report["audio"]["silent"]
    path = tmp_path / f"{instrument}.mid"
    export_midi(song, path)
    midi = mido.MidiFile(path)
    assert next(m for m in midi.tracks[1] if m.type == "program_change").program == program
