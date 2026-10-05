"""Independent frequency, timing, causality and export checks for dance effects."""

import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import (
    Chorus,
    Distortion,
    Ducker,
    Filter,
    Note,
    Phaser,
    Song,
    TempoChange,
    Track,
    Tremolo,
    inspect_score,
    render_audio,
)
from audio_as_code._modulation_effects import _beat_clock
from audio_as_code.effects import apply_effects, effects_tail

EFFECTS = [Filter(), Distortion(), Chorus(), Phaser(), Tremolo(), Ducker(trigger_beats=(0, 1))]


def song(effects=()):
    return Song(
        beats=2,
        sample_rate=22050,
        tracks=[Track(name="Test", instrument="sine", notes=[Note(duration=1)], effects=effects)],
    )


@pytest.mark.parametrize("effect", EFFECTS, ids=lambda e: e.type)
def test_effects_render_round_trip_bypass_and_report_unsupported_midi(effect):
    original = song()
    altered = song((effect,))
    assert Song.model_validate_json(altered.model_dump_json()) == altered
    result = render_audio(altered)
    assert np.isfinite(result.audio).all() and not result.report["audio"]["silent"]
    np.testing.assert_array_equal(result.audio, render_audio(altered).audio)
    bypass = song((effect.model_copy(update={"mix": 0}),))
    assert bypass.render_seconds == original.render_seconds
    np.testing.assert_array_equal(render_audio(bypass).audio, render_audio(original).audio)
    assert any(i["code"] == "midi_effects_not_exported" for i in inspect_score(altered)["issues"])


@pytest.mark.parametrize("mode", ["lowpass", "highpass", "bandpass"])
def test_filter_matches_analog_prototype_with_bilinear_prewarping(mode):
    rate, cutoff, hz, resonance = 22050, 1400, 3300, 0.4
    t = np.arange(rate) / rate
    source = np.tile(np.sin(2 * np.pi * hz * t)[:, None], (1, 2)).astype(np.float32)
    effect = Filter(mode=mode, cutoff_hz=cutoff, resonance=resonance)
    actual = apply_effects(source, (effect,), rate)[:, 0]
    ratio = np.tan(np.pi * hz / rate) / np.tan(np.pi * cutoff / rate)
    q = 0.5 + 7.5 * resonance
    numerator = {"lowpass": 1, "highpass": ratio**2, "bandpass": ratio / q}[mode]
    expected = numerator / abs(1 - ratio**2 + 1j * ratio / q)
    # Projection onto the source frequency measures steady-state amplitude.
    tail = actual[rate // 2 :]
    measured = abs(np.sum(tail * np.exp(-2j * np.pi * hz * t[rate // 2 :]))) * 2 / len(tail)
    assert measured == pytest.approx(expected, rel=0.002)


@pytest.mark.parametrize("effect", [Filter(cutoff_hz=30, resonance=1), Chorus(), Phaser()])
def test_filters_are_causal_with_no_wrapped_attack_and_a_bounded_tail(effect):
    rate = 22050
    size = round((0.1 + effects_tail((effect,))) * rate)
    source = np.zeros((size, 2), np.float32)
    source[100, 0] = 1
    result = apply_effects(source, (effect,), rate)
    assert np.all(result[:100] == 0) and np.all(result[:, 1] == 0)
    assert np.max(abs(result[-32:])) < 1e-4


def test_filter_sweep_changes_spectrum_and_extremes_are_finite():
    rate = 22050
    source = np.random.default_rng(7).standard_normal((rate, 2)).astype(np.float32) * 0.05
    effect = Filter(cutoff_hz=30, end_cutoff_hz=20000, sweep_seconds=0.01, resonance=1)
    result = apply_effects(source, (effect,), rate)
    assert np.isfinite(result).all() and np.max(abs(result)) < 4


def test_tempo_synced_modulation_continues_through_tempo_changes_and_tails():
    score = Song(
        beats=4,
        bpm=120,
        sample_rate=22050,
        tempo_map=[TempoChange(beat=2, bpm=60)],
        tracks=[Track(name="Clock")],
    )
    beats = _beat_clock(score, 0, 22050 * 4 + 1, 22050)
    for seconds, expected in ((0, 0), (0.5, 1), (1, 2), (2, 3), (3, 4), (4, 5)):
        assert beats[round(seconds * 22050)] == pytest.approx(expected)
    source = np.ones((len(beats), 2), np.float32)
    out = apply_effects(source, (Tremolo(period_beats=1, depth=1),), 22050, score)
    assert out[round(1.5 * 22050), 0] == pytest.approx(0, abs=1e-7)
    assert out[2 * 22050, 0] == pytest.approx(1)


def test_ducker_is_triggered_on_score_clock_and_recovers_smoothly():
    score = song()
    source = np.ones((22050, 2), np.float32)
    effect = Ducker(trigger_beats=(1,), depth=0.8, attack_seconds=0.01, release_seconds=0.2)
    out = apply_effects(source, (effect,), 22050, score)[:, 0]
    assert np.all(out[:11025] == 1)
    assert out[round(0.51 * 22050)] == pytest.approx(0.2, abs=1e-5)
    assert out[round(0.72 * 22050)] == 1
    assert np.max(abs(np.diff(out))) < 0.007
    for values in ((1, 0), (0, 0)):
        with pytest.raises(ValidationError, match="strictly increasing"):
            Ducker(trigger_beats=values)
    with pytest.raises(ValidationError, match="before the song ends"):
        song((Ducker(trigger_beats=(2,)),))


def test_chorus_makes_width_and_distortion_adds_harmonics_without_chunk_seams():
    rate = 22050
    t = np.arange(140000) / rate
    source = np.tile((0.5 * np.sin(2 * np.pi * 220 * t))[:, None], (1, 2)).astype(np.float32)
    chorus = apply_effects(source, (Chorus(),), rate)
    assert np.sqrt(np.mean((chorus[:, 0] - chorus[:, 1]) ** 2)) > 0.05
    saturated = apply_effects(source, (Distortion(drive=8, mix=1),), rate)
    # Band-limiting a saturated discontinuous endpoint can overshoot. It is not
    # a brickwall limiter; the renderer still handles mix headroom separately.
    assert np.max(abs(saturated)) <= 1.2
    assert np.max(abs(saturated[100:-100])) <= 1.01
    for boundary in (65536, 131072):
        assert np.max(abs(np.diff(saturated[boundary - 10 : boundary + 10, 0]))) < 0.3
    segment = saturated[rate : rate * 2, 0]
    third = abs(np.sum(segment * np.exp(-2j * np.pi * 660 * np.arange(rate) / rate))) / rate
    assert third > 0.05


@pytest.mark.parametrize("hz,maximum_error", [(1700, 0.0001), (3700, 0.0005), (6300, 0.004)])
def test_distortion_matches_high_rate_analytic_reference(hz, maximum_error):
    rate, drive = 22050, 6
    time = np.arange(rate) / rate
    source = np.tile((0.7 * np.sin(2 * np.pi * hz * time))[:, None], (1, 2)).astype(np.float32)
    result = apply_effects(source, (Distortion(drive=drive, mix=1),), rate)[:, 0]
    # Independent 32x analytic input and ideal FFT low-pass, with no production
    # interpolator/decimator. Integer cycles exclude spectral leakage.
    high_time = np.arange(rate * 32) / (rate * 32)
    high = np.tanh(drive * 0.7 * np.sin(2 * np.pi * hz * high_time)) / np.tanh(drive)
    spectrum = np.fft.rfft(high)
    spectrum[np.fft.rfftfreq(len(high), 1 / (rate * 32)) > rate * 0.45] = 0
    expected = np.fft.irfft(spectrum, n=len(high))[::32]
    assert np.sqrt(np.mean((result[200:-200] - expected[200:-200]) ** 2)) < maximum_error


def test_distortion_has_no_chunk_reset_and_retains_its_finite_tail():
    from audio_as_code._electronic_dsp import decimate, interpolate

    rate = 22050
    source = np.zeros((132000, 2), np.float32)
    source[65535:65538, 0] = (0.3, 0.9, -0.6)
    source[131071:131074, 1] = (0.2, -0.7, 0.1)
    effect = Distortion(drive=4, mix=1)
    result = apply_effects(source, (effect,), rate)
    # Whole-array processing is independent of production chunk boundaries.
    for channel in (0, 1):
        expected = decimate(np.tanh(4 * interpolate(source[:, channel])) / np.tanh(4))
        np.testing.assert_allclose(result[:, channel], expected, atol=6e-8, rtol=0)
    assert np.max(abs(result[65538:65602, 0])) > 0.0001
