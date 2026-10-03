import itertools

import mido
import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import Note, Song, Tone, Track, export_midi, get_instrument, render_audio
from audio_as_code.instruments import KIT_NOTES
from audio_as_code.orchestra import EXTRA_INSTRUMENTS, synthesize
from audio_as_code.render import _voice


@pytest.mark.parametrize("instrument", sorted(EXTRA_INSTRUMENTS))
def test_models_are_repeatable_finite_nonzero_and_gated(instrument):
    info = get_instrument(instrument)
    audio = _voice(instrument, info.preview_pitch, 22050, 22050, 91)
    np.testing.assert_array_equal(audio, _voice(instrument, info.preview_pitch, 22050, 22050, 91))
    assert np.all(np.isfinite(audio))
    assert 0.005 < np.max(np.abs(audio)) < 1
    assert np.all(audio[[0, -1]] == 0)


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
@pytest.mark.parametrize("instrument", sorted(EXTRA_INSTRUMENTS))
def test_extreme_notes_and_controls_remain_bounded(instrument, rate):
    info = get_instrument(instrument)
    limits = {
        "brightness": 1,
        "decay_seconds": 20,
        "pluck_position": 0.05,
        "breath": 1,
        "vibrato_depth_cents": 100,
        "vibrato_rate_hz": 12,
        "glide_semitones": 24,
        "detune_cents": 40,
    }
    tone = Tone(**{key: value for key, value in limits.items() if key in info.tone_controls})
    for pitch in [0, 100, 127]:
        audio = _voice(instrument, pitch, rate // 4, rate, 3, tone=tone)
        assert np.all(np.isfinite(audio))
        assert np.max(np.abs(audio)) < 1.1
        if info.midi_note is None and 440 * 2 ** ((pitch - 69) / 12) >= rate / 2:
            assert not np.any(audio)


@pytest.mark.parametrize(
    "instrument",
    [
        "electric_guitar",
        "bass_guitar",
        "harp",
        "ukulele",
        "banjo",
        "harpsichord",
        "piano",
        "violin",
        "flute",
        "clarinet",
        "trumpet",
        "timpani",
    ],
)
@pytest.mark.parametrize("pitch", [40, 60, 76])
def test_melodic_fundamentals_are_tuned(instrument, pitch):
    info = get_instrument(instrument)
    tone = Tone(vibrato_depth_cents=0) if "vibrato_depth_cents" in info.tone_controls else None
    rate = 22050
    audio = _voice(instrument, pitch, rate * 2, rate, 19, tone=tone)[rate // 3 : rate + rate // 2]
    size = len(audio) * 8
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio)), n=size))
    expected = 440 * 2 ** ((pitch - 69) / 12)
    low, high = round(expected * 0.96 * size / rate), round(expected * 1.04 * size / rate)
    index = low + np.argmax(spectrum[low : high + 1])
    a, b, c = np.log(spectrum[index - 1 : index + 2] + 1e-20)
    correction = 0.5 * (a - c) / (a - 2 * b + c)
    measured = (index + correction) * rate / size
    assert abs(1200 * np.log2(measured / expected)) < 5, (instrument, pitch, measured)


@pytest.mark.parametrize(
    "instrument",
    [
        "piano",
        "electric_guitar",
        "bass_guitar",
        "harp",
        "xylophone",
        "vibraphone",
        "glockenspiel",
        "toms",
        "cymbal",
        "timpani",
    ],
)
def test_decay_changes_audible_tail(instrument):
    info = get_instrument(instrument)
    short = _voice(instrument, info.preview_pitch, 44100, 22050, 7, tone=Tone(decay_seconds=0.3))
    long = _voice(instrument, info.preview_pitch, 44100, 22050, 7, tone=Tone(decay_seconds=5))
    assert np.mean(long[22050:] ** 2) > 100 * np.mean(short[22050:] ** 2)


@pytest.mark.parametrize(
    "instrument", ["violin", "flute", "clarinet", "trumpet", "organ", "theremin"]
)
def test_held_instruments_sustain_and_expressive_controls_change_output(instrument):
    base = _voice(instrument, 60, 44100, 22050, 7)
    assert np.mean(base[30000:40000] ** 2) > 0.3 * np.mean(base[10000:20000] ** 2)
    info = get_instrument(instrument)
    for key in info.tone_controls:
        values = {
            "brightness": 0,
            "breath": 1,
            "vibrato_depth_cents": 80,
            "vibrato_rate_hz": 8,
            "glide_semitones": 12,
        }
        settings = {key: values[key]}
        if key == "vibrato_rate_hz":
            settings["vibrato_depth_cents"] = 20
        changed = _voice(instrument, 60, 44100, 22050, 7, tone=Tone(**settings))
        assert not np.array_equal(base, changed), (instrument, key)


def test_named_woodwind_spectra_are_distinct():
    spectra = {}
    for instrument in ["flute", "clarinet", "saxophone", "oboe", "bassoon"]:
        audio = _voice(instrument, 60, 22050, 22050, 7, tone=Tone(breath=0, vibrato_depth_cents=0))
        spectrum = np.abs(np.fft.rfft(audio[8192:16384] * np.hanning(8192)))
        spectra[instrument] = spectrum / np.linalg.norm(spectrum)
    for first, second in itertools.combinations(spectra, 2):
        assert np.linalg.norm(spectra[first] - spectra[second]) > 0.08, (first, second)


def test_kit_routes_notes_and_preserves_them_in_midi(tmp_path):
    notes = [Note(pitch=pitch, start=i, duration=0.4) for i, pitch in enumerate(KIT_NOTES)]
    song = Song(beats=8, tracks=[Track(name="Kit", instrument="drum_machine", notes=notes)])
    for pitch, instrument in KIT_NOTES.items():
        np.testing.assert_array_equal(
            _voice("drum_machine", pitch, 4000, 22050, 17),
            _voice(instrument, pitch, 4000, 22050, 17),
        )
    assert not render_audio(song).report["audio"]["silent"]
    path = tmp_path / "kit.mid"
    export_midi(song, path)
    events = [event for event in mido.MidiFile(path).tracks[1] if event.type == "note_on"]
    assert [event.note for event in events] == list(KIT_NOTES)
    assert all(event.channel == 9 for event in events)
    with pytest.raises(ValidationError, match="drum_machine pitch"):
        Track(name="Kit", instrument="drum_machine", notes=[Note(pitch=61)])


def test_kit_and_individual_drum_cannot_overlap_same_midi_note(tmp_path):
    song = Song(
        tracks=[
            Track(name="Kit", instrument="drum_machine", notes=[Note(pitch=36)]),
            Track(name="Kick", instrument="kick", notes=[Note()]),
        ]
    )
    with pytest.raises(ValueError, match="overlapping percussion MIDI pitch 36"):
        export_midi(song, tmp_path / "collision.mid")


def test_new_controls_reject_invalid_and_unsupported_values():
    for value in [float("nan"), float("inf"), -1, 1.1]:
        with pytest.raises(ValidationError):
            Tone(breath=value)
    with pytest.raises(ValidationError, match="breath is not supported"):
        Track(name="Piano", instrument="piano", tone=Tone(breath=0.5))
    with pytest.raises(ValidationError, match="pluck_position is not supported"):
        Track(name="Violin", instrument="violin", tone=Tone(pluck_position=0.2))
    with pytest.raises(ValidationError):
        Tone(glide_semitones=25)


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_theremin_glide_reenters_playable_band_without_aliasing(rate):
    # The first octave of this glide lies above Nyquist. It must be muted
    # there, then recover once the instantaneous pitch enters the audio band.
    audio = synthesize(
        "theremin",
        rate * 0.2,
        rate,
        rate,
        7,
        0.8,
        Tone(glide_semitones=24, vibrato_depth_cents=0),
    )
    assert np.max(np.abs(audio[: round(rate * 0.02)])) < 1e-12
    assert np.sqrt(np.mean(audio[rate // 2 :] ** 2)) > 0.3
    # A steady tail should contain the two audible intended partials, with
    # no folded third/fourth partials. Use a lower bound for the fundamental.
    tail = audio[round(rate * 0.75) :]
    spectrum = np.abs(np.fft.rfft(tail * np.hanning(len(tail)))) ** 2
    frequencies = np.fft.rfftfreq(len(tail), 1 / rate)
    intended = (np.abs(frequencies - rate * 0.2) < rate * 0.004) | (
        np.abs(frequencies - rate * 0.4) < rate * 0.008
    )
    assert np.sum(spectrum[~intended]) < 0.001 * np.sum(spectrum)


def test_detuned_synth_retains_in_band_oscillators_at_top_register():
    rate = 22050
    audio = synthesize("synthesizer", rate * 0.485, rate, rate, 7, 0.8, Tone(detune_cents=40))
    # The upper detuned fundamental is above the guard; the other two
    # fundamentals remain playable and must not be discarded with it.
    assert np.sqrt(np.mean(audio**2)) > 0.003


@pytest.mark.parametrize("instrument", ["organ", "synthesizer"])
def test_high_partial_guard_does_not_jump_remaining_voice_level(instrument):
    rate = 22050
    # The second mode crosses the old hard exclusion boundary. Compare
    # sustained RMS on either side, keeping the pitch displacement tiny.
    levels = []
    for multiplier in [0.9999, 1.0001]:
        audio = synthesize(
            instrument,
            rate * 0.245 * multiplier,
            rate,
            rate,
            7,
            0.8,
            Tone(detune_cents=0) if instrument == "synthesizer" else None,
        )
        levels.append(np.sqrt(np.mean(audio[rate // 2 :] ** 2)))
    assert max(levels) / min(levels) < 1.005


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_membrane_pitch_relaxation_recovers_mode_inside_guard_band(rate):
    # The strike starts above the guard but settles below it. A fixed guard
    # based on the strike's maximum pitch incorrectly silenced the whole mode.
    audio = synthesize("timpani", rate * 0.46, rate, rate, 7, 0.8, Tone(decay_seconds=5))
    tail = audio[round(rate * 0.25) : round(rate * 0.5)]
    assert np.sqrt(np.mean(tail**2)) > 0.03
    spectrum = np.abs(np.fft.rfft(tail * np.hanning(len(tail))))
    measured = np.argmax(spectrum) * rate / len(tail)
    assert abs(measured - rate * 0.46) < 6
