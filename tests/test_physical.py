import json

import mido
import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import Note, Song, Tone, Track, export_midi, render_audio
from audio_as_code.physical import synthesize


def test_original_engine_does_not_substitute_guitar_for_new_string_models():
    with pytest.raises(ValueError, match="original physical/modal engine"):
        synthesize("piano", 220, 1000, 22050, 7, 0.8, None)


def voice(instrument, *, pitch="A3", rate=22050, velocity=0.8, tone=None, seed=9):
    song = Song(
        bpm=60,
        beats=2,
        sample_rate=rate,
        seed=seed,
        tracks=[
            Track(
                name="Instrument",
                instrument=instrument,
                tone=tone,
                gain=1,
                notes=[Note(pitch=pitch, duration=2, velocity=velocity)],
            ),
        ],
    )
    return render_audio(song)


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
@pytest.mark.parametrize("pitch", [40, 57, 76])
def test_string_fundamental_is_tuned_across_rates_and_registers(rate, pitch):
    result = voice("guitar", pitch=pitch, rate=rate)
    segment = result.audio[round(rate * 0.15) : round(rate * 1.7), 0]
    size = 8 * len(segment)
    spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment)), n=size))
    expected = 440 * 2 ** ((pitch - 69) / 12)
    low, high = round(expected * 0.95 * size / rate), round(expected * 1.05 * size / rate)
    index = low + np.argmax(spectrum[low : high + 1])
    a, b, c = np.log(spectrum[index - 1 : index + 2] + 1e-20)
    correction = 0.5 * (a - c) / (a - 2 * b + c)
    measured = (index + correction) * rate / size
    cents = abs(1200 * np.log2(measured / expected))
    assert cents < 5, (rate, pitch, measured, expected, cents)


@pytest.mark.parametrize("instrument", ["guitar", "marimba", "bell"])
def test_physical_voices_are_repeatable_finite_and_fade(instrument):
    a, b = voice(instrument), voice(instrument)
    np.testing.assert_array_equal(a.audio, b.audio)
    assert np.all(np.isfinite(a.audio))
    assert a.report["audio"]["peak"] > 0.03
    assert a.report["audio"]["clipped_samples"] == 0
    assert np.all(a.audio[[0, -1]] == 0)


@pytest.mark.parametrize("instrument", ["guitar", "marimba", "bell"])
def test_decay_control_changes_energy_later_in_note(instrument):
    short = voice(instrument, tone=Tone(decay_seconds=0.25)).audio[22050:, 0]
    long = voice(instrument, tone=Tone(decay_seconds=4)).audio[22050:, 0]
    assert np.mean(long**2) > 100 * np.mean(short**2)


@pytest.mark.parametrize("instrument", ["guitar", "marimba", "bell"])
def test_velocity_changes_timbre_as_well_as_volume(instrument):
    soft = voice(instrument, velocity=0.3).audio[:, 0]
    hard = voice(instrument, velocity=0.9).audio[:, 0]
    assert not np.allclose(soft / 0.3, hard / 0.9, atol=1e-5)
    assert np.sqrt(np.mean(hard**2)) > np.sqrt(np.mean(soft**2))


def test_pluck_position_and_seed_change_excitation():
    bridge = voice("guitar", tone=Tone(pluck_position=0.07)).audio
    middle = voice("guitar", tone=Tone(pluck_position=0.4)).audio
    assert not np.array_equal(bridge, middle)
    assert not np.array_equal(voice("guitar", seed=1).audio, voice("guitar", seed=2).audio)


@pytest.mark.parametrize("instrument", ["guitar", "marimba", "bell"])
def test_brightness_changes_spectral_energy(instrument):
    def high_band(brightness):
        audio = voice(instrument, tone=Tone(brightness=brightness)).audio[:4096, 0]
        spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio)))) ** 2
        frequencies = np.fft.rfftfreq(len(audio), 1 / 22050)
        return spectrum[frequencies > 600].sum() / spectrum.sum()

    assert high_band(1) > high_band(0)


def test_tone_validation_and_score_round_trip():
    with pytest.raises(ValidationError, match="tone controls"):
        Track(name="Lead", instrument="sine", tone=Tone())
    with pytest.raises(ValidationError, match="pluck_position"):
        Track(name="Bell", instrument="bell", tone=Tone(pluck_position=0.1))
    for options in [
        {"brightness": 2},
        {"decay_seconds": 0},
        {"pluck_position": 0},
        {"brightness": float("nan")},
    ]:
        with pytest.raises(ValidationError):
            Tone(**options)
    song = Song(
        tracks=[
            Track(
                name="Guitar",
                instrument="guitar",
                tone=Tone(brightness=0.7, decay_seconds=4, pluck_position=0.1),
            )
        ]
    )
    assert Song.model_validate_json(song.model_dump_json()) == song
    assert json.loads(song.model_dump_json())["tracks"][0]["tone"]["brightness"] == 0.7


@pytest.mark.parametrize("instrument", ["guitar", "marimba", "bell"])
def test_extreme_registers_remain_finite_and_inaudible_above_nyquist(instrument):
    for rate in [22050, 44100, 48000]:
        for pitch in [0, 100, 127]:
            result = voice(instrument, pitch=pitch, rate=rate)
            assert np.all(np.isfinite(result.audio))
            assert result.report["audio"]["clipped_samples"] == 0
            if 440 * 2 ** ((pitch - 69) / 12) >= rate / 2:
                assert result.report["audio"]["silent"]


def test_new_midi_programs_and_tone_warning(tmp_path):
    song = Song(
        tracks=[
            Track(name=name, instrument=name, tone=Tone(), notes=[Note()])
            for name in ["guitar", "marimba", "bell"]
        ]
    )
    path = tmp_path / "physical.mid"
    report = export_midi(song, path)
    midi = mido.MidiFile(path)
    assert [
        event.program for track in midi.tracks for event in track if event.type == "program_change"
    ] == [24, 12, 14]
    assert "tone controls are not exported" in report["warnings"][0]
