"""Custom patches are data, and share the ordinary rendering/effect contract."""

import json

import numpy as np
import pytest
from pydantic import ValidationError

from audio_as_code import (
    Chorus,
    CustomInstrument,
    Delay,
    Distortion,
    Ducker,
    Filter,
    FMLayer,
    ModalLayer,
    ModalPartial,
    NoiseLayer,
    Note,
    OscillatorLayer,
    PatchFilter,
    Phaser,
    Reverb,
    Song,
    Tone,
    Track,
    Tremolo,
    export_midi,
    inspect_score,
    instrument_catalog,
    render,
    render_audio,
    render_preview_audio,
)
from audio_as_code.cli import main


def patch_song(layers=None, **kwargs):
    patch = CustomInstrument(name="Glass", layers=layers or [OscillatorLayer()])
    return Song(
        sample_rate=22050,
        beats=2,
        seed=37,
        custom_instruments={"custom:glass": patch},
        tracks=[
            Track(name="Glass", instrument="custom:glass", notes=[Note(pitch="A4", duration=2)])
        ],
        **kwargs,
    )


def test_roundtrip_immutability_hash_and_discovery(tmp_path, capsys):
    song = patch_song()
    song.save(tmp_path / "patch.json")
    loaded = Song.load(tmp_path / "patch.json")
    assert song == loaded
    assert song.model_copy(deep=True) == song
    with pytest.raises(TypeError):
        song.custom_instruments["custom:other"] = song.custom_instruments["custom:glass"]
    a, b = render_audio(song), render_audio(loaded)
    np.testing.assert_array_equal(a.audio, b.audio)
    assert a.report == b.report
    assert len(instrument_catalog()["instruments"]) == 70
    catalog = instrument_catalog(custom_instruments=song.custom_instruments)
    custom = catalog["instruments"][-1]
    assert custom["origin"] == "user_defined" and custom["status"] == "available"
    assert main(["instruments", "--score", str(tmp_path / "patch.json")]) == 0
    assert json.loads(capsys.readouterr().out)["instruments"][-1] == json.loads(json.dumps(custom))
    assert inspect_score(song)["tracks"][0]["instrument_origin"] == "user_defined"


@pytest.mark.parametrize(
    "layer",
    [
        OscillatorLayer(waveform="sine"),
        OscillatorLayer(waveform="triangle"),
        OscillatorLayer(waveform="saw"),
        OscillatorLayer(waveform="pulse"),
        ModalLayer(partials=[ModalPartial(), ModalPartial(ratio=2.7, amplitude=0.2)]),
        FMLayer(index=0),
    ],
)
@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_pitch_envelope_and_finite_output(layer, rate):
    song = patch_song([layer]).model_copy(update={"sample_rate": rate})
    result = render_audio(song, normalize=False)
    data = result.audio[:, 0]
    spectrum = np.abs(np.fft.rfft(data[round(0.2 * rate) : round(0.8 * rate)]))
    frequency = np.argmax(spectrum) / 0.6
    assert frequency == pytest.approx(440, abs=2)
    assert np.isfinite(data).all() and np.max(np.abs(data)) > 0.01
    assert result.audio.shape[0] == round(1.1 * rate)
    assert data[0] == data[-1] == 0


def test_layer_seed_isolation_and_velocity_gain():
    song = patch_song([NoiseLayer(), FMLayer()])
    original = render_audio(song, normalize=False).audio
    changed = render_audio(song.model_copy(update={"seed": 38}), normalize=False).audio
    assert not np.array_equal(original, changed)
    extra = song.model_copy(update={"tracks": (*song.tracks, Track(name="Rest"))})
    np.testing.assert_array_equal(render_audio(extra, normalize=False).audio, original)
    quiet = song.model_copy(update={"tracks": (song.tracks[0].model_copy(update={"gain": 0.3}),)})
    np.testing.assert_array_equal(render_audio(quiet, normalize=False).audio, original * 0.5)


@pytest.mark.parametrize(
    "effect",
    [
        Delay(),
        Reverb(),
        Filter(),
        Distortion(),
        Chorus(),
        Phaser(),
        Tremolo(),
        Ducker(trigger_beats=[0, 1]),
    ],
)
def test_every_effect_on_custom_voice_and_bypass(effect, tmp_path):
    dry = patch_song([NoiseLayer()])
    track = dry.tracks[0]
    wet = dry.model_copy(update={"tracks": (track.model_copy(update={"effects": (effect,)}),)})
    result = render_audio(wet, normalize=False)
    original = render_audio(dry, normalize=False).audio
    assert np.isfinite(result.audio).all()
    assert len(result.audio) >= len(original)
    assert not np.array_equal(result.audio[: len(original)], original)
    bypass = dry.model_copy(
        update={
            "tracks": (
                track.model_copy(update={"effects": (effect.model_copy(update={"mix": 0}),)}),
            )
        }
    )
    np.testing.assert_array_equal(
        render_audio(bypass, normalize=False).audio[: len(original)], original
    )
    preview = render_preview_audio(wet, normalize=False, start_seconds=0.2, duration_seconds=0.3)
    np.testing.assert_array_equal(preview.audio, result.audio[4410:11025])
    report = render(wet, tmp_path / "mix.wav", stems_dir=tmp_path / "stems", normalize=False)
    assert report["stems"][0]["audio"]["peak"] > 0
    assert (tmp_path / "mix.wav").read_bytes() == (tmp_path / "stems/01.wav").read_bytes()


def test_controls_and_release_precedence():
    song = patch_song([OscillatorLayer(waveform="saw")])
    patch = song.custom_instruments["custom:glass"]
    filtered = song.model_copy(
        update={
            "custom_instruments": {
                "custom:glass": patch.model_copy(update={"filter": PatchFilter(cutoff_hz=100)})
            }
        }
    )
    assert render_audio(filtered).report["audio"]["rms"] < render_audio(song).report["audio"]["rms"]
    track = song.tracks[0].model_copy(update={"release_seconds": 0.3})
    assert song.model_copy(update={"tracks": (track,)}).render_seconds == pytest.approx(1.3)
    track = track.model_copy(
        update={"notes": (track.notes[0].model_copy(update={"release_seconds": 0}),)}
    )
    assert song.model_copy(update={"tracks": (track,)}).render_seconds == 1
    for index in (0, 8):
        result = render_audio(patch_song([FMLayer(index=index)]))
        if index == 0:
            plain = result.audio
        else:
            assert not np.allclose(plain, result.audio)


@pytest.mark.parametrize("pitch", [0, 36, 69, 100, 127])
def test_extreme_patch_stability(pitch):
    song = patch_song(
        [
            OscillatorLayer(waveform="pulse", pulse_width=0.05, tuning_semitones=48),
            FMLayer(index=12, ratio=8),
            ModalLayer(partials=[ModalPartial(ratio=64, decay_seconds=20)]),
            NoiseLayer(),
        ]
    )
    data = song.model_dump()
    data["tracks"][0]["notes"][0]["pitch"] = pitch
    data["custom_instruments"]["custom:glass"]["filter"] = PatchFilter(resonance=1).model_dump()
    result = render_audio(Song.model_validate(data))
    assert np.isfinite(result.audio).all()
    assert result.report["audio"]["peak"] <= 0.951


def test_invalid_patches_and_undefined_names():
    with pytest.raises(ValidationError, match="undefined custom"):
        Song(tracks=[Track(name="Missing", instrument="custom:missing")])
    with pytest.raises(ValidationError):
        Track(name="Typo", instrument="custom:INVALID")
    with pytest.raises(ValidationError, match="unknown instrument"):
        Track(name="Typo", instrument="sien")
    with pytest.raises(ValidationError, match="do not support"):
        Track(name="Patch", instrument="custom:test", tone=Tone())
    for data in (
        {"layers": []},
        {"layers": [{"type": "sample", "path": "x.wav"}]},
        {"layers": [{"type": "fm", "index": float("nan")}]},
        {"layers": [OscillatorLayer().model_dump()] * 9},
    ):
        with pytest.raises(ValidationError):
            CustomInstrument.model_validate({"name": "Bad", **data})


def test_midi_requires_explicit_mapping_and_preserves_file(tmp_path):
    song = patch_song()
    assert not inspect_score(song)["readiness"]["midi"]["ready"]
    dest = tmp_path / "patch.mid"
    dest.write_bytes(b"existing")
    with pytest.raises(ValueError, match="midi_program"):
        export_midi(song, dest)
    assert dest.read_bytes() == b"existing"
    data = song.model_dump()
    data["custom_instruments"]["custom:glass"]["midi_program"] = 80
    mapped = Song.model_validate(data)
    assert inspect_score(mapped)["readiness"]["midi"]["ready"]
    assert "Custom patches" in str(export_midi(mapped, dest)["warnings"])


def test_mix_arrangement_and_automation_preserve_patch_data():
    from audio_as_code import (
        Arrangement,
        Automation,
        AutomationPoint,
        Mastering,
        MixEdit,
        Pattern,
        Section,
        TruePeakLimiter,
        apply_mix,
        audition_song,
    )

    song = patch_song(mastering=Mastering(limiter=TruePeakLimiter()))
    revised = apply_mix(song, [MixEdit(tracks=["Glass"], trim_db=-6)]).song
    assert revised.custom_instruments == song.custom_instruments
    assert revised.mastering == song.mastering
    audition = audition_song(revised, mute=["Glass"])
    assert render_audio(audition).report["audio"]["silent"]
    arrangement = Arrangement(song, (Section("Phrase", 0, 2),))
    replaced = arrangement.replace_section("Phrase", {"Glass": Pattern.sequence(["A5"], step=2)})
    assert replaced.song.custom_instruments == song.custom_instruments
    assert replaced.song.mastering == song.mastering
    track = song.tracks[0].model_copy(
        update={
            "automation": (
                Automation(
                    parameter="gain",
                    points=[AutomationPoint(beat=0, value=0), AutomationPoint(beat=2, value=0)],
                ),
            )
        }
    )
    assert render_audio(song.model_copy(update={"tracks": (track,)})).report["audio"]["silent"]
