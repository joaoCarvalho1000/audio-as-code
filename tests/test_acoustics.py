import numpy as np
import pytest

from audio_as_code._fir import convolve_causal
from audio_as_code._voices import _electronic_voice
from audio_as_code.acoustics import colored_noise, modulate_noise, resonant_body, slow_variation
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
    t = np.arange(rate * 2) / rate
    # Known spectral probes isolate intended sidebands (7/9 kHz) from a
    # 5 kHz input that would fold to 9050 Hz under naive multiplication.
    noise = np.sin(2 * np.pi * 1000 * t) + np.sin(2 * np.pi * 5000 * t)
    phase = 2 * np.pi * 8000 * t
    result = modulate_noise(noise, phase, 8000, rate, 0.25)
    # Measure after filter startup: the generated causal FIR has a finite
    # transition, rather than a whole-note circular brickwall transform.
    added = np.abs(np.fft.rfft((result - noise)[rate:])) / rate
    assert added[7000] > 0.06 and added[9000] > 0.06
    assert added[9050] < 1e-7
    assert added[3000] < 1e-7
    np.testing.assert_array_equal(result, modulate_noise(noise, phase, 8000, rate, 0.25))
    np.testing.assert_array_equal(noise, modulate_noise(noise, phase, rate, rate, 0.25))


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_colored_excitation_does_not_change_when_a_note_is_extended(rate):
    long = colored_noise(rate * 2, rate, 83, 700, 7500)
    for frames in (1, 127, 4097, rate):
        np.testing.assert_array_equal(long[:frames], colored_noise(frames, rate, 83, 700, 7500))
    assert 0.03 < np.sqrt(np.mean(long**2)) < 0.3
    assert abs(np.mean(long)) < 0.0002


def test_modulated_excitation_does_not_anticipate_future_noise():
    rate = 22050
    noise = np.zeros(rate)
    noise[4000] = 1
    phase = 2 * np.pi * 440 * np.arange(rate) / rate
    result = modulate_noise(noise, phase, 450, rate, 0.25)
    assert np.max(abs(result[:4000])) < 1e-14
    assert np.max(abs(result[4001:5000])) > 0.01
    short = modulate_noise(noise[:10000], phase[:10000], 450, rate, 0.25)
    np.testing.assert_allclose(short, result[:10000], atol=1e-14, rtol=0)


def test_block_filter_matches_direct_linear_convolution_across_boundaries():
    rng = np.random.default_rng(31)
    signal = rng.standard_normal(14513)
    kernel = rng.standard_normal(537) / 537
    expected = np.convolve(signal, kernel)[: len(signal)]
    np.testing.assert_allclose(convolve_causal(signal, kernel), expected, atol=2e-16, rtol=0)
    assert convolve_causal(np.zeros(0), kernel).shape == (0,)


def test_basic_oscillator_fades_before_nyquist_without_folded_fundamental():
    rate = 22050
    levels = []
    for fraction in (0.44, 0.46, 0.48, 0.49, 0.51):
        signal = _electronic_voice("sine", rate * fraction, rate, rate, 1, 0.8)
        levels.append(np.sqrt(np.mean(signal**2)))
    assert levels[0] > levels[1] > levels[2] > 0
    assert levels[3] == levels[4] == 0
