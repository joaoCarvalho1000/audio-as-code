"""Exact numerical contracts for allocation-saving modal evaluation."""

import numpy as np
import pytest

from audio_as_code.orchestra import _forced_piano_pole


@pytest.mark.parametrize("frames", [0, 1, 7, 100, 44100])
@pytest.mark.parametrize("contact", [1e-8, 0.003, 2.0])
@pytest.mark.parametrize("pole", [-0.7 + 172.8j, -12 + 2764.6j])
def test_piano_buffer_reuse_preserves_finite_force_response(frames, contact, pole):
    # Retain the original closed-form expression as an exact rounding contract:
    # changing operation order or using real exp/sin instead of complex exp can
    # change seeded renders even when the mathematical result is equivalent.
    t = np.arange(frames) / 44100
    t.flags.writeable = False
    attacking = t < contact
    u = t[attacking]
    expected = np.zeros(frames, dtype=np.complex128)
    released = 0j
    for weight, offset in ((1, 0), (-0.5, 2 * np.pi / contact), (-0.5, -2 * np.pi / contact)):
        denominator = pole - 1j * offset
        expected[attacking] += (
            weight * np.exp(1j * offset * u) * np.expm1(denominator * u) / denominator
        )
        released += (
            weight * np.exp(1j * offset * contact) * np.expm1(denominator * contact) / denominator
        )
    expected[~attacking] = released * np.exp(pole * (t[~attacking] - contact))
    np.testing.assert_array_equal(_forced_piano_pole(t, pole, contact), expected / contact)
