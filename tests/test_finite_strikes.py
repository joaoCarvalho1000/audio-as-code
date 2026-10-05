"""Independent force-integration and instrument checks for finite strikes."""

import numpy as np
import pytest

from audio_as_code import Tone
from audio_as_code.acoustics import struck_mode
from audio_as_code.render import _voice


@pytest.mark.parametrize(
    "frequency,damping,contact", [(220, 3, 0.004), (500, 20, 0.002), (27.5, 69, 0.008)]
)
def test_strike_matches_numerical_force_integration(frequency, damping, contact):
    # Dense trapezoidal quadrature is independent of the closed-form integral.
    t = np.linspace(0, 0.03, 151)
    expected = []
    for now in t:
        s = np.linspace(0, min(now, contact), 2001)
        force = (1 - np.cos(2 * np.pi * s / contact)) / contact
        impulse = np.exp(-damping * (now - s)) * np.sin(2 * np.pi * frequency * (now - s))
        expected.append(np.trapezoid(force * impulse, s))
    np.testing.assert_allclose(struck_mode(t, frequency, damping, contact), expected, atol=2e-7)


def test_strike_is_bounded_and_independent_of_sample_rate_and_duration():
    t = np.arange(4800) / 48000
    signal = struck_mode(t, 440, 4, 0.003)
    assert signal[0] == 0
    assert np.max(np.abs(signal)) <= 1
    np.testing.assert_array_equal(signal[::2], struck_mode(t[::2], 440, 4, 0.003))
    np.testing.assert_array_equal(signal[:100], struck_mode(t[:100], 440, 4, 0.003))
    # A vanishing contact converges to an impulse, not a lost sub-sample hit.
    np.testing.assert_allclose(
        struck_mode(t, 440, 4, 1e-8), np.exp(-4 * t) * np.sin(2 * np.pi * 440 * t), atol=1.4e-5
    )


@pytest.mark.parametrize(
    "instrument",
    [
        "piano",
        "marimba",
        "bell",
        "clavinet",
        "electric_piano",
        "xylophone",
        "vibraphone",
        "glockenspiel",
    ],
)
def test_struck_voice_tuning_brightness_and_velocity(instrument):
    rate = 22050
    for pitch in (48, 60, 79):
        audio = _voice(instrument, pitch, rate * 2, rate, 4217, tone=Tone(decay_seconds=4))
        expected = 440 * 2 ** ((pitch - 69) / 12)
        tail = audio[rate // 10 : rate]
        size = 8 * len(tail)
        spectrum = np.abs(np.fft.rfft(tail * np.hanning(len(tail)), n=size))
        lo, hi = int(expected * 0.97 * size / rate), int(expected * 1.03 * size / rate)
        k = lo + np.argmax(spectrum[lo:hi])
        a, b, c = np.log(spectrum[k - 1 : k + 2] + 1e-30)
        measured = (k + 0.5 * (a - c) / (a - 2 * b + c)) * rate / size
        assert abs(1200 * np.log2(measured / expected)) < 5
    dark = _voice(instrument, 60, rate, rate, 4217, tone=Tone(brightness=0))
    bright = _voice(instrument, 60, rate, rate, 4217, tone=Tone(brightness=1))

    def centroid(audio):
        power = abs(np.fft.rfft(audio[: rate // 5] * np.hanning(rate // 5))) ** 2
        return np.sum(power * np.fft.rfftfreq(rate // 5, 1 / rate)) / np.sum(power)

    assert centroid(bright) > centroid(dark)
    soft = _voice(instrument, 60, rate, rate, 4217, velocity=0.2)
    hard = _voice(instrument, 60, rate, rate, 4217, velocity=0.9)
    # _voice handles timbre; the renderer applies the velocity gain separately.
    assert np.mean((0.9 * hard) ** 2) > np.mean((0.2 * soft) ** 2)
