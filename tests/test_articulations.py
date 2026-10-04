"""Opt-in source gestures: capabilities, spectral behavior and score integration."""

import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import Note, Song, Tone, Track, get_instrument, list_instruments, render_audio
from audio_as_code._orchestra_profiles import HELD_RELEASE
from audio_as_code._voices import _voice
from audio_as_code.orchestra import synthesize
from audio_as_code.render import _canonical_score

SUPPORTED = (
    "violin",
    "viola",
    "cello",
    "double_bass",
    "flute",
    "clarinet",
    "saxophone",
    "oboe",
    "bassoon",
    "trumpet",
    "trombone",
    "french_horn",
    "tuba",
)


def rms(audio):
    return float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))


def centroid(audio, rate):
    power = abs(np.fft.rfft(audio * np.hanning(len(audio)))) ** 2
    return np.sum(power * np.fft.rfftfreq(len(audio), 1 / rate)) / np.sum(power)


def test_capabilities_are_explicit_and_reject_every_unimplemented_instrument():
    assert {i.id for i in list_instruments() if i.articulations} == set(SUPPORTED)
    assert set(HELD_RELEASE) == set(SUPPORTED)
    for info in list_instruments():
        if info.id in SUPPORTED:
            assert info.articulations == ("soft", "accented")
            for articulation in info.articulations:
                Track(name="Gesture", instrument=info.id, articulation=articulation)
                Track(name="Gesture", instrument=info.id, notes=[Note(articulation=articulation)])
        else:
            with pytest.raises(ValidationError, match="articulation.*not supported"):
                Track(name="No fallback", instrument=info.id, articulation="soft")
            with pytest.raises(ValidationError, match="note 0: articulation.*not supported"):
                Track(name="No fallback", instrument=info.id, notes=[Note(articulation="accented")])
            with pytest.raises(ValueError, match="not supported"):
                _voice(info.id, info.preview_pitch, 100, 22050, 0, articulation="soft")


@pytest.mark.parametrize("value", ["legato", "pizzicato", "normal", "", True, 0])
def test_unknown_gestures_are_rejected(value):
    with pytest.raises(ValidationError):
        Note(articulation=value)


@pytest.mark.parametrize("instrument", SUPPORTED)
def test_attack_changes_spectrum_and_timing_without_changing_sustained_tone(instrument):
    rate = 22050
    pitch = get_instrument(instrument).preview_pitch
    args = (instrument, pitch, rate * 2, rate, 52)
    soft = _voice(*args, articulation="soft")
    accented = _voice(*args, articulation="accented")
    # Accent arrives earlier and contains more upper-band energy even after
    # normalizing loudness. This rules out an overall volume-only gesture.
    attack = slice(rate // 50, rate // 7)
    assert rms(accented[attack]) > 1.3 * rms(soft[attack])
    assert centroid(accented[attack], rate) > centroid(soft[attack], rate)
    # Neither articulation substitutes a permanently different preset spectrum.
    sustain = slice(int(rate * 1.6), int(rate * 1.8))
    assert abs(rms(soft[sustain]) / rms(accented[sustain]) - 1) < 0.07
    np.testing.assert_array_equal(soft, _voice(*args, articulation="soft"))
    assert not np.array_equal(
        soft, _voice(instrument, pitch, rate * 2, rate, 53, articulation="soft")
    )


@pytest.mark.parametrize("instrument", SUPPORTED)
@pytest.mark.parametrize("articulation", ["soft", "accented"])
def test_note_off_changes_partial_decay_and_preserves_the_held_interval(instrument, articulation):
    rate = 22050
    frequency = 440 * 2 ** ((get_instrument(instrument).preview_pitch - 69) / 12)
    tone = Tone(vibrato_depth_cents=0)
    args = (instrument, frequency, rate * 2, rate, 52, 0.8, tone)
    ongoing = synthesize(*args, articulation=articulation)
    released = synthesize(*args, articulation=articulation, held_frames=rate)
    # Equal lengths keep the FFT-shaped seeded noise identical in this comparison.
    np.testing.assert_array_equal(ongoing[: rate + 1], released[: rate + 1])
    near = slice(rate + rate // 50, rate + rate // 10)
    late = slice(rate + rate // 3, rate + rate // 2)
    assert centroid(released[near], rate) < centroid(ongoing[near], rate)
    assert rms(released[late]) < 0.06 * rms(ongoing[late])
    assert np.max(abs(np.diff(released[rate - 20 : rate + 20]))) < 0.5


@pytest.mark.parametrize("instrument", SUPPORTED)
@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_articulation_tuning_and_finite_short_extreme_controls(instrument, rate):
    pitch = get_instrument(instrument).preview_pitch
    for articulation in ("soft", "accented"):
        audio = _voice(
            instrument,
            pitch,
            round(rate * 1.6),
            rate,
            17,
            tone=Tone(vibrato_depth_cents=0),
            articulation=articulation,
        )
        tail = audio[rate // 2 : rate + rate // 2]
        size = len(tail) * 8
        spectrum = abs(np.fft.rfft(tail * np.hanning(len(tail)), n=size))
        expected = 440 * 2 ** ((pitch - 69) / 12)
        lo, hi = int(expected * 0.97 * size / rate), int(expected * 1.03 * size / rate)
        k = lo + np.argmax(spectrum[lo : hi + 1])
        a, b, c = np.log(spectrum[k - 1 : k + 2] + 1e-30)
        measured = (k + 0.5 * (a - c) / (a - 2 * b + c)) * rate / size
        assert abs(1200 * np.log2(measured / expected)) < 5
        for frames in (1, 2, 3, 127, rate // 3):
            extreme = _voice(
                instrument,
                pitch,
                frames,
                rate,
                17,
                velocity=1,
                tone=Tone(brightness=1, vibrato_depth_cents=100, vibrato_rate_hz=12),
                held_frames=max(1, frames // 2) if frames > 1 else None,
                articulation=articulation,
            )
            assert np.isfinite(extreme).all()
            assert extreme[0] == extreme[-1] == 0
            assert np.max(abs(extreme)) < 1.1


@pytest.mark.parametrize("release", [0, 0.2])
def test_track_inheritance_note_override_and_default_identity(release):
    base = dict(name="Violin", instrument="violin", release_seconds=release)

    def score(track):
        return Song(beats=2, sample_rate=22050, tracks=[track])

    implicit = score(Track(**base, notes=[Note(duration=2)]))
    explicit = score(Track(**base, articulation=None, notes=[Note(duration=2, articulation=None)]))
    inherited = score(Track(**base, articulation="soft", notes=[Note(duration=2)]))
    overridden = score(
        Track(
            **base,
            articulation="accented",
            notes=[Note(duration=2, articulation="soft")],
        )
    )
    local = score(Track(**base, notes=[Note(duration=2, articulation="soft")]))
    default_result = render_audio(implicit)
    explicit_result = render_audio(explicit)
    np.testing.assert_array_equal(default_result.audio, explicit_result.audio)
    assert default_result.report["score_sha256"] == explicit_result.report["score_sha256"]
    canonical = _canonical_score(explicit)["tracks"][0]
    assert "articulation" not in canonical and "articulation" not in canonical["notes"][0]
    expected = render_audio(inherited)
    np.testing.assert_array_equal(expected.audio, render_audio(overridden).audio)
    np.testing.assert_array_equal(expected.audio, render_audio(local).audio)
    assert not np.array_equal(expected.audio, default_result.audio)
    assert expected.report["score_sha256"] != default_result.report["score_sha256"]
    assert expected.audio.shape[0] == round((1 + release) * 22050)
    assert expected.report["audio"]["clipped_samples"] == 0
