import numpy as np
import pytest

from audio_as_code.acoustics import modulate_noise, resonant_body, slow_variation
from audio_as_code.render import _voice


def test_body_filter_is_causal_bounded_and_has_a_driven_tail():
    signal = np.zeros(22050)
    signal[8190] = 1
    result = resonant_body(signal, 22050, ((210, 0.15, 1),), wet=0.5)
    assert np.max(np.abs(result[:8190])) < 1e-14
    assert 0.49 < result[8190] <= 0.51
    assert np.max(np.abs(result[8191:10000])) > 0.001
    assert np.max(np.abs(result)) <= 1
    np.testing.assert_array_equal(result, resonant_body(signal, 22050, ((210, 0.15, 1),), wet=0.5))


def test_slow_variation_is_bounded_and_duration_independent():
    short = slow_variation(np.arange(22050) / 22050, 4)
    long = slow_variation(np.arange(44100) / 22050, 4)
    np.testing.assert_array_equal(short, long[:22050])
    assert np.max(np.abs(long)) <= 1
    assert np.max(np.abs(np.diff(long))) < 0.001
    assert not np.array_equal(short, slow_variation(np.arange(22050) / 22050, 5))


@pytest.mark.parametrize(
    "instrument", ["electric_guitar", "harp", "piano", "violin", "flute", "trumpet"]
)
def test_instrument_motion_changes_with_seed_but_is_reproducible(instrument):
    a = _voice(instrument, 60, 22050, 22050, 8)
    b = _voice(instrument, 60, 22050, 22050, 9)
    assert not np.array_equal(a, b)
    np.testing.assert_array_equal(a, _voice(instrument, 60, 22050, 22050, 8))


@pytest.mark.parametrize("instrument", ["kick", "snare", "hat"])
def test_drum_velocity_changes_attack_shape_not_just_gain(instrument):
    soft = _voice(instrument, 60, 11025, 22050, 6, velocity=0.25)
    hard = _voice(instrument, 60, 11025, 22050, 6, velocity=0.95)
    assert not np.allclose(soft, hard)
    assert np.max(np.abs(hard)) < 1.1


def test_long_bowed_release_is_smooth_and_does_not_extend_note():
    rate = 22050
    signal = _voice("cello", 48, rate, rate, 4)
    assert len(signal) == rate and signal[-1] == 0
    assert np.mean(signal[-round(0.02 * rate) :] ** 2) < 0.01 * np.mean(
        signal[round(0.6 * rate) : round(0.7 * rate)] ** 2
    )


def test_pitch_modulated_noise_keeps_in_band_sidebands_without_foldover():
    rate = 22050
    t = np.arange(rate) / rate
    # Known spectral probes isolate intended sidebands (7/9 kHz) from a
    # 5 kHz input that would fold to 9050 Hz under naive multiplication.
    noise = np.sin(2 * np.pi * 1000 * t) + np.sin(2 * np.pi * 5000 * t)
    phase = 2 * np.pi * 8000 * t
    result = modulate_noise(noise, phase, 8000, rate, 0.25)
    added = np.abs(np.fft.rfft(result - noise)) / rate
    assert added[7000] > 0.06 and added[9000] > 0.06
    assert added[9050] < 1e-10
    assert added[3000] < 1e-10
    np.testing.assert_array_equal(result, modulate_noise(noise, phase, 8000, rate, 0.25))
    np.testing.assert_array_equal(noise, modulate_noise(noise, phase, rate, rate, 0.25))
