"""Level regressions: preserve touch, headroom and authored mix gain relationships."""

import json

import numpy as np
import pytest

from audio_as_code import Automation, Note, Song, Tone, Track, get_instrument, render_audio
from audio_as_code._voices import _voice
from examples.instrument_balance import audit, metrics, mixed_scores, pitches_for

CHANGED = (
    "sine",
    "triangle",
    "pad",
    "sub_bass",
    "theremin",
    "flute",
    "recorder",
    "piano",
    "banjo",
    "harpsichord",
    "mandolin",
    "trance_pluck",
    "synthesizer",
)


def test_audit_rejects_invalid_comparisons_before_replacing_audio(tmp_path):
    before = tmp_path / "before"
    before.mkdir()
    (before / "piano.wav").write_bytes(b"keep baseline")
    (before / "report.json").write_text(json.dumps({"sample_rate": 44100}))
    with pytest.raises(ValueError, match="differ"):
        audit(tmp_path, "before", "before", 44100, False)
    with pytest.raises(ValueError, match="same sample rate"):
        audit(tmp_path, "after", "before", 22050, False)
    assert (before / "piano.wav").read_bytes() == b"keep baseline"
    assert not (tmp_path / "after").exists()


def rms(audio):
    return np.sqrt(np.mean(audio.astype(np.float64) ** 2))


@pytest.mark.parametrize("instrument", CHANGED)
def test_register_touch_ordering_and_default_headroom(instrument):
    rate = 22050
    for pitch in pitches_for(get_instrument(instrument)):
        levels = []
        for velocity in (0.35, 0.65, 1.0):
            signal = _voice(instrument, pitch, rate, rate, 2026, velocity) * velocity
            assert np.isfinite(signal).all()
            assert 0 < np.max(np.abs(signal)) < 0.95
            levels.append(rms(signal))
        assert levels[0] < levels[1] < levels[2]
        assert levels[2] / levels[0] > 2, "Calibration must retain a useful touch range"


@pytest.mark.parametrize("instrument", CHANGED)
@pytest.mark.parametrize("rate", (44100, 48000))
def test_strong_bright_notes_remain_finite_and_have_headroom(instrument, rate):
    info = get_instrument(instrument)
    tone = Tone(brightness=1) if "brightness" in info.tone_controls else None
    for pitch in pitches_for(info):
        for seed in (7, 171):
            signal = _voice(instrument, pitch, rate // 2, rate, seed, 1, tone)
            assert np.isfinite(signal).all()
            assert 0 < np.max(np.abs(signal)) < 1
            np.testing.assert_array_equal(
                signal, _voice(instrument, pitch, rate // 2, rate, seed, 1, tone)
            )


def test_sustained_outliers_are_within_six_db_of_synth_peer():
    def level(instrument):
        x = _voice(instrument, 60, 22050, 22050, 2026, 0.65) * 0.65
        return metrics(x, 22050)["active_rms_dbfs"]

    peer = level("sync_lead")
    for instrument in ("sine", "triangle", "pad", "theremin", "synthesizer"):
        assert abs(level(instrument) - peer) < 6


def test_woodwind_level_spread_stays_below_four_db():
    levels = []
    for instrument in ("flute", "clarinet", "saxophone", "oboe", "bassoon", "recorder"):
        info = get_instrument(instrument)
        x = _voice(instrument, info.preview_pitch, 22050, 22050, 2026, 0.65) * 0.65
        levels.append(metrics(x, 22050)["active_rms_dbfs"])
    assert max(levels) - min(levels) < 4


@pytest.mark.parametrize(
    "instrument",
    ("violin", "viola", "cello", "double_bass", "trumpet", "trombone", "french_horn", "tuba"),
)
def test_short_accents_retain_more_onset_energy_without_clipping(instrument):
    info = get_instrument(instrument)
    rate, frames = 22050, round(0.08 * 22050)
    normal = _voice(instrument, info.preview_pitch, frames, rate, 2026, 0.8)
    accent = _voice(
        instrument, info.preview_pitch, frames, rate, 2026, 0.8, articulation="accented"
    )
    assert rms(normal) > 0
    assert rms(accent) > 1.4 * rms(normal)
    assert np.isfinite(accent).all() and np.max(np.abs(accent)) < 1
    assert accent[0] == accent[-1] == 0


def test_quiet_piano_has_useful_onset_without_flattening_its_decay():
    x = _voice("piano", 60, 22050, 22050, 2026, 0.65) * 0.65
    assert -23 < metrics(x, 22050)["onset_400ms_rms_dbfs"] < -19
    assert rms(x[:4410]) > 2 * rms(x[-4410:])


@pytest.mark.parametrize("instrument", ("piano", "sine", "flute", "trance_pluck"))
@pytest.mark.parametrize("expressive", (False, True))
def test_user_gain_is_linear_with_static_and_automated_controls(instrument, expressive):
    track = Track(
        name="Voice",
        instrument=instrument,
        gain=0.4,
        notes=[Note(duration=1)],
        release_seconds=0.1 if expressive else 0,
    )
    song = Song(beats=2, sample_rate=22050, tracks=[track])
    original = render_audio(song, normalize=False)
    louder_track = track.model_copy(update={"gain": 0.8})
    louder = render_audio(song.model_copy(update={"tracks": (louder_track,)}), normalize=False)
    np.testing.assert_allclose(louder.audio, original.audio * 2, rtol=2e-7, atol=1e-8)
    if expressive:
        lane = Automation(parameter="gain", points=[{"beat": 0, "value": 0.4}])
        automated = track.model_copy(update={"automation": (lane,)})
        result = render_audio(song.model_copy(update={"tracks": (automated,)}), normalize=False)
        np.testing.assert_allclose(result.audio, original.audio, rtol=2e-7, atol=1e-8)


def test_active_metric_excludes_added_silence_and_rejects_near_silence():
    x = _voice("hat", 42, 22050, 22050, 2026, 0.65)
    padded = np.concatenate((x, np.zeros(22050)))
    assert metrics(x, 22050)["active_rms_dbfs"] == metrics(padded, 22050)["active_rms_dbfs"]
    assert metrics(x * 1e-8, 22050)["active_rms_dbfs"] is None


@pytest.mark.parametrize("name", ("winds", "plucked"))
def test_representative_ensembles_have_headroom_without_master_normalization(name):
    song = mixed_scores(22050)[name]
    result = render_audio(song, normalize=False)
    stems = [
        render_audio(song.model_copy(update={"tracks": (track,)}), normalize=False).audio
        for track in song.tracks
    ]
    np.testing.assert_array_equal(result.audio, np.sum(stems, axis=0))
    assert result.report["gain_applied"] == 1
    assert result.report["audio"]["clipped_samples"] == 0
    assert 0.01 < result.report["audio"]["peak"] < 0.7
