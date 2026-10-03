import wave

import numpy as np
import pytest

from audio_as_code import Note, Song, Track, analyze_wav, render, render_audio


def song_with(*tracks, **kwargs):
    return Song(bpm=120, beats=2, sample_rate=22050, tracks=tracks, **kwargs)


def test_tuning_duration_and_envelope():
    song = song_with(Track(name="Tone", instrument="sine", notes=[Note(pitch="A4", duration=2)]))
    result = render_audio(song)
    assert result.audio.shape == (22050, 2)
    spectrum = np.abs(np.fft.rfft(result.audio[:, 0]))
    assert np.argmax(spectrum) == 440
    assert np.all(result.audio[[0, -1]] == 0)
    assert result.report["audio"]["rms"] > 0.1


def test_noise_is_repeatable_and_seeded():
    track = Track(name="Snare", instrument="snare", notes=[Note(duration=0.5)])
    a = render_audio(song_with(track, seed=7))
    b = render_audio(song_with(track, seed=7))
    c = render_audio(song_with(track, seed=8))
    np.testing.assert_array_equal(a.audio, b.audio)
    assert a.report == b.report
    assert not np.array_equal(a.audio, c.audio)
    assert a.report["score_sha256"] != c.report["score_sha256"]


def test_absolute_note_placement_pan_and_silence():
    song = song_with(Track(name="Right", instrument="sine", pan=1, notes=[Note(start=1)]))
    result = render_audio(song)
    np.testing.assert_allclose(result.audio[:, 0], 0, atol=1e-15)
    assert np.max(np.abs(result.audio[:11025])) == 0
    assert np.max(np.abs(result.audio[11026:, 1])) > 0
    silence = render_audio(song_with(Track(name="Rest")))
    assert silence.report["audio"]["silent"]
    assert silence.report["audio"]["rms_dbfs"] is None
    assert silence.report["warnings"]


def test_peak_attenuation_and_clipping_reports(tmp_path):
    loud = song_with(
        Track(name="Loud", instrument="sine", gain=1, notes=[Note(pitch="A4", velocity=1)] * 8)
    )
    report = render(loud, tmp_path / "safe.wav")
    assert report["before_gain"]["clipped_samples"] > 0
    assert report["gain_applied"] < 1
    assert report["audio"]["peak"] <= 0.951
    assert report["wav"]["full_scale_samples"] == 0
    clipped = render(loud, tmp_path / "clipped.wav", normalize=False)
    assert clipped["audio"]["clipped_samples"] > 0
    assert clipped["wav"]["full_scale_samples"] > 0


def test_wav_bytes_stems_and_analysis(tmp_path):
    song = song_with(
        Track(name="../Bass", instrument="bass", pan=-0.4, notes=[Note(pitch="C2")]),
        Track(name="Lead", instrument="pluck", pan=0.5, notes=[Note(pitch="E4")]),
    )
    report = render(song, tmp_path / "mix.wav", stems_dir=tmp_path / "stems")
    render(song, tmp_path / "again.wav")
    assert (tmp_path / "mix.wav").read_bytes() == (tmp_path / "again.wav").read_bytes()
    assert report["wav"] == analyze_wav(tmp_path / "mix.wav")
    assert {p.name for p in (tmp_path / "stems").iterdir()} == {"01.wav", "02.wav"}

    def pcm(path):
        with wave.open(str(path), "rb") as stream:
            assert stream.getsampwidth() == 2
            assert stream.getnchannels() == 2
            assert stream.getnframes() == 22050
            return np.frombuffer(stream.readframes(22050), dtype="<i2").astype(np.int32)

    summed = pcm(tmp_path / "stems" / "01.wav") + pcm(tmp_path / "stems" / "02.wav")
    np.testing.assert_allclose(summed, pcm(tmp_path / "mix.wav"), atol=1)


def test_stem_path_collision_does_not_write(tmp_path):
    song = song_with(Track(name="Lead"))
    with pytest.raises(ValueError, match="same path"):
        render(song, tmp_path / "01.wav", stems_dir=tmp_path)
    assert not (tmp_path / "01.wav").exists()


def test_render_limits_and_revalidation():
    with pytest.raises(ValueError, match="300 seconds"):
        render_audio(Song(beats=1000, tracks=[Track(name="Long")]))
    song = song_with(Track(name="Lead"))
    with pytest.raises(ValueError):
        render_audio(song.model_copy(update={"bpm": 0}))


def test_all_voices_are_finite_audible_and_fade():
    for instrument in ["sine", "triangle", "pluck", "bass", "pad", "kick", "snare", "hat"]:
        result = render_audio(
            song_with(Track(name="Voice", instrument=instrument, notes=[Note(duration=2)]))
        )
        assert np.all(np.isfinite(result.audio)), instrument
        assert result.report["audio"]["peak"] > 0.01, instrument
        assert np.all(result.audio[[0, -1]] == 0), instrument
