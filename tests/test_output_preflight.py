"""Invalid Python output paths must be rejected before synthesis or any writes."""

import importlib

import pytest

from audio_as_code import Song, Track, render


@pytest.mark.parametrize("conflict", ["blocked_parent", "stem_directory", "mix_parent"])
def test_python_render_preserves_existing_mix_on_invalid_stem_path(tmp_path, monkeypatch, conflict):
    destination = tmp_path / "mix.wav"
    original = b"previous render"
    destination.write_bytes(original)
    stems = tmp_path / "stems"
    if conflict == "blocked_parent":
        stems.write_bytes(b"existing non-directory")
    elif conflict == "stem_directory":
        (stems / "02.wav").mkdir(parents=True)
    else:
        stems = destination / "stems"

    def unexpected_synthesis(*args, **kwargs):
        pytest.fail("invalid output paths must fail before synthesis")

    monkeypatch.setattr(
        importlib.import_module("audio_as_code.render"), "render_audio", unexpected_synthesis
    )
    song = Song(beats=1, tracks=[Track(name="One"), Track(name="Two")])
    with pytest.raises(ValueError):
        render(song, destination, stems_dir=stems)
    assert destination.read_bytes() == original
    assert not (stems / "01.wav").exists()


def test_python_render_rejects_future_file_directory_collision_without_creating_outputs(tmp_path):
    # The mix would create the stems directory, but occupy the first stem's parent.
    destination = tmp_path / "stems"
    song = Song(beats=1, tracks=[Track(name="One")])
    with pytest.raises(ValueError, match="output directory"):
        render(song, destination, stems_dir=destination)
    assert not destination.exists()
