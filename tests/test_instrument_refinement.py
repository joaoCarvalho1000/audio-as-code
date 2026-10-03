"""Independent physics, register and control checks for the refined extra voices."""

import numpy as np
import pytest

from audio_as_code import Tone
from audio_as_code.orchestra import _bowed_transfer, _forced_piano_pole, _piano_poles
from audio_as_code.render import _voice


def test_coupled_piano_matches_independent_time_domain_integration():
    frequency, damping, contact = 110.0, 8.0, 0.003
    detunes = (-0.9, 0.0, 0.9)
    rate = 192000
    t = np.arange(3841) / rate
    poles, residues = _piano_poles(frequency, damping, detunes)
    actual = sum(
        r * _forced_piano_pole(t, p, contact) for p, r in zip(poles, residues, strict=True)
    )
    # Integrate three coupled complex string amplitudes directly with RK4;
    # this does not use eigenvectors or the closed-form hammer integral.
    matrix = np.diag(-0.28 * damping + 2j * np.pi * frequency * 2 ** (np.array(detunes) / 1200))
    matrix -= np.full((3, 3), 0.72 * damping / 3)

    def derivative(time, state):
        force = (1 - np.cos(2 * np.pi * time / contact)) / contact if time < contact else 0
        return matrix @ state + force

    state = np.zeros(3, dtype=complex)
    expected = np.zeros(len(t), dtype=complex)
    dt = 1 / rate
    for index, time in enumerate(t[:-1]):
        a = derivative(time, state)
        b = derivative(time + dt / 2, state + a * dt / 2)
        c = derivative(time + dt / 2, state + b * dt / 2)
        d = derivative(time + dt, state + c * dt)
        state += dt / 6 * (a + 2 * b + 2 * c + d)
        expected[index + 1] = np.mean(state)
    np.testing.assert_allclose(actual, expected, atol=2e-8)


@pytest.mark.parametrize("frequency", [27.5, 110, 261.625565, 1760, 4186])
@pytest.mark.parametrize("damping", [0.2, 2, 20, 200])
def test_piano_coupling_is_passive_and_preserves_unison_frequency_band(frequency, damping):
    poles, residues = _piano_poles(frequency, damping, (-0.9, 0, 0.9))
    assert np.all(poles.real <= -0.28 * damping + 1e-9)
    cents = 1200 * np.log2(poles.imag / (2 * np.pi * frequency))
    assert np.max(np.abs(cents)) <= 0.900001
    assert np.sum(residues) == pytest.approx(1)
    # Common motion and differential motion have distinct decay rates.
    assert np.ptp(poles.real) > 0


def test_body_resonance_has_both_gain_and_phase_and_remains_bounded():
    formants = ((470, 230, 0.6), (2800, 900, 1.5))
    low = _bowed_transfer(2000, formants)
    high = _bowed_transfer(4000, formants)
    assert low.imag > 0 and high.imag < 0
    for frequency in np.geomspace(10, 24000, 500):
        assert 1 <= abs(_bowed_transfer(frequency, formants)) <= 3.1


@pytest.mark.parametrize(
    "instrument,pitches",
    [
        ("piano", [21, 33, 45, 60, 72, 84, 96]),
        ("violin", [55, 67, 79]),
        ("viola", [48, 60, 72]),
        ("cello", [36, 48, 60]),
        ("double_bass", [28, 40, 52]),
    ],
)
def test_refined_register_fundamentals_stay_tuned(instrument, pitches):
    rate = 22050
    tone = None if instrument == "piano" else Tone(vibrato_depth_cents=0)
    for pitch in pitches:
        audio = _voice(instrument, pitch, rate * 2, rate, 813, tone=tone)
        tail = audio[rate // 4 : rate + rate // 2]
        size = len(tail) * 8
        spectrum = abs(np.fft.rfft(tail * np.hanning(len(tail)), n=size))
        expected = 440 * 2 ** ((pitch - 69) / 12)
        lo, hi = int(expected * 0.97 * size / rate), int(expected * 1.03 * size / rate)
        k = lo + np.argmax(spectrum[lo : hi + 1])
        a, b, c = np.log(spectrum[k - 1 : k + 2] + 1e-30)
        measured = (k + 0.5 * (a - c) / (a - 2 * b + c)) * rate / size
        assert abs(1200 * np.log2(measured / expected)) < 5, (instrument, pitch, measured)


@pytest.mark.parametrize(
    "instrument,pitch",
    [
        ("piano", 60),
        ("violin", 55),
        ("viola", 48),
        ("cello", 36),
        ("double_bass", 28),
    ],
)
def test_refined_controls_determinism_short_and_long_notes(instrument, pitch):
    rate = 22050
    base = _voice(instrument, pitch, rate, rate, 8)
    np.testing.assert_array_equal(base, _voice(instrument, pitch, rate, rate, 8, tone=Tone()))
    np.testing.assert_array_equal(base, _voice(instrument, pitch, rate, rate, 8))
    assert not np.array_equal(base, _voice(instrument, pitch, rate, rate, 9))
    for frames in [1, 2, 3, rate * 8]:
        tone = (
            Tone(brightness=1, decay_seconds=20)
            if instrument == "piano"
            else Tone(brightness=1, vibrato_depth_cents=100, vibrato_rate_hz=12)
        )
        audio = _voice(instrument, pitch, frames, rate, 8, tone=tone)
        assert len(audio) == frames and np.isfinite(audio).all()
        assert np.max(abs(audio)) < 1.1
        assert audio[0] == audio[-1] == 0


@pytest.mark.parametrize("instrument,pitch", [("piano", 60), ("violin", 55), ("cello", 48)])
def test_brightness_and_velocity_change_spectrum_without_loudness_substitution(instrument, pitch):
    rate = 22050

    def centroid(audio):
        audio = audio[rate // 20 : rate // 3]
        power = abs(np.fft.rfft(audio * np.hanning(len(audio)))) ** 2
        return np.sum(power * np.fft.rfftfreq(len(audio), 1 / rate)) / np.sum(power)

    dark = _voice(instrument, pitch, rate, rate, 8, tone=Tone(brightness=0))
    bright = _voice(instrument, pitch, rate, rate, 8, tone=Tone(brightness=1))
    assert centroid(bright) > 1.1 * centroid(dark)
    soft = _voice(instrument, pitch, rate, rate, 8, velocity=0.2)
    hard = _voice(instrument, pitch, rate, rate, 8, velocity=0.95)
    assert centroid(hard) > centroid(soft)
    assert np.mean((0.95 * hard) ** 2) > np.mean((0.2 * soft) ** 2)
