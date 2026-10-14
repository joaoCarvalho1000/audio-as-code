"""Rhythm helpers retain ordinary score timing, controls and deterministic output."""

import numpy as np
import pytest

from audio_as_code import Note, Pattern, Song, Track, render_audio


def test_euclidean_spacing_rotation_and_silence():
    rhythm = Pattern.euclidean(3, 8, pitch=36, gate=1)
    assert [note.start for note in rhythm.notes] == [0, 1.5, 3]
    assert rhythm.beats == 4
    assert [note.start for note in Pattern.euclidean(3, 8, rotation=1).notes] == [0.5, 2, 3.5]
    assert Pattern.euclidean(3, 8, rotation=-1) == Pattern.euclidean(3, 8, rotation=7)
    assert Pattern.euclidean(0, 8) == Pattern((), 4)
    assert len(Pattern.euclidean(8, 8).notes) == 8
    for steps in range(1, 24):
        for pulses in range(1, steps + 1):
            starts = [n.start for n in Pattern.euclidean(pulses, steps, step=1).notes]
            gaps = [b - a for a, b in zip(starts, starts[1:] + [steps], strict=True)]
            assert len(starts) == pulses
            assert max(gaps) - min(gaps) <= 1


def test_swing_warps_boundaries_and_preserves_controls_and_length():
    phrase = Pattern.sequence([["C4", "E4"], "G4", None, "C5"], step=0.5, gate=1)
    swung = phrase.swing()
    assert [n.start for n in swung.notes] == pytest.approx([0, 0, 2 / 3, 1 + 2 / 3])
    assert [n.duration for n in swung.notes] == pytest.approx([2 / 3, 2 / 3, 1 / 3, 1 / 3])
    assert swung.beats == phrase.beats
    assert phrase.swing(0.5) == phrase
    assert swung.repeat(2).notes[len(swung.notes)].start == 2
    held = Pattern((Note(start=0.25, duration=1.5, release_seconds=0.7),), 2)
    result = held.swing().notes[0]
    assert result.start == pytest.approx(1 / 3)
    assert result.start + result.duration == pytest.approx(1 + 5 / 6)
    assert result.release_seconds == 0.7
    assert held.notes[0].start == 0.25


def test_reverse_mirrors_intervals_and_rest_positions():
    phrase = Pattern.sequence([None, ["C4", "E4"], "G4", None, None], gate=1)
    result = phrase.reverse()
    assert [(n.pitch, n.start) for n in result.notes] == [("G4", 2), ("C4", 3), ("E4", 3)]
    assert result.reverse() == phrase
    assert Pattern((), 4).reverse() == Pattern((), 4)
    note = Note(start=0.25, duration=0.5, velocity=0.3, release_seconds=0.7)
    assert Pattern((note,), 2).reverse().notes[0].model_dump() == {
        **note.model_dump(),
        "start": 1.25,
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pulses": True},
        {"steps": False},
        {"rotation": 0.5},
        {"pulses": -1},
        {"pulses": 9},
        {"steps": 0},
        {"pitch": "invalid"},
        {"gate": 0},
        {"velocity": 0},
        {"step": float("inf")},
    ],
)
def test_euclidean_rejects_invalid_input_even_when_silent(kwargs):
    with pytest.raises(ValueError):
        Pattern.euclidean(**{"pulses": 0, "steps": 8, **kwargs})


@pytest.mark.parametrize("value", [0, -1, True, "0.5", None, float("nan"), float("inf")])
@pytest.mark.parametrize("parameter", ["ratio", "step"])
def test_swing_validates_silent_phrases(parameter, value):
    with pytest.raises(ValueError):
        Pattern((), 4).swing(**{parameter: value})


def test_swing_rejects_collapsed_steps_and_incomplete_pairs():
    with pytest.raises(ValueError):
        Pattern((), 4).swing(1)
    with pytest.raises(ValueError, match="complete pairs"):
        Pattern((), 1.5).swing()


def test_rhythm_roundtrips_and_renders_deterministically():
    base = Pattern.euclidean(3, 8, pitch="C4").accent([1, 0.7]).swing()
    phrase = base.repeat(2, variations={1: base.reverse()})
    song = Song(
        title="Rhythm check",
        beats=8,
        tracks=(Track(name="Pulse", instrument="pluck", notes=phrase.at(0)),),
    )
    restored = Song.model_validate_json(song.model_dump_json())
    assert restored == song
    first = render_audio(song).audio
    second = render_audio(restored).audio
    assert np.array_equal(first, second)
    assert np.isfinite(first).all()
    assert np.max(np.abs(first)) > 0


def test_accents_follow_grid_rests_and_chords_not_note_indices():
    phrase = Pattern.sequence([["C4", "E4"], None, "G4", "C5"], step=0.5, velocity=0.5)
    result = phrase.accent([1, 0.5, 0.8, 0.6])
    assert [n.velocity for n in result.notes] == pytest.approx([0.5, 0.5, 0.4, 0.3])
    assert [n.start for n in result.notes] == [0, 0, 1, 1.5]
    assert result.beats == 2
    assert phrase.notes[-1].velocity == 0.5
    decimal = Pattern((Note(start=0.3, duration=0.1, velocity=0.5),), 1)
    assert decimal.accent([1, 0.5], step=0.1).notes[0].velocity == 0.25
    with pytest.raises(ValueError):
        phrase.accent([3])


@pytest.mark.parametrize("weights", [[], "12", None, [0], [-1], [True], [float("nan")]])
def test_invalid_accent_grid_rejected_for_silence(weights):
    with pytest.raises(ValueError):
        Pattern((), 4).accent(weights)


def test_repeat_variations_keep_bar_positions_and_inputs():
    base = Pattern.sequence(["C4", None], gate=1)
    fill = Pattern.sequence(["D4", "E4"], gate=1)
    result = base.repeat(4, variations={1: fill, 3: Pattern((), 2)})
    assert [(n.pitch, n.start) for n in result.notes] == [
        ("C4", 0),
        ("D4", 2),
        ("E4", 3),
        ("C4", 4),
    ]
    assert result.beats == 8
    assert base.repeat(2, variations={}) == base.repeat(2)
    assert fill.notes[0].start == 0


@pytest.mark.parametrize(
    "variations",
    [
        [],
        {True: Pattern((), 2)},
        {-1: Pattern((), 2)},
        {2: Pattern((), 2)},
        {0: None},
        {0: Pattern((), 3)},
    ],
)
def test_invalid_repetition_variations(variations):
    with pytest.raises(ValueError):
        Pattern((), 2).repeat(2, variations=variations)


def test_near_grid_boundaries_do_not_snap_intentional_offsets():
    early = Pattern((Note(start=0.5 - 1e-11, duration=0.2, velocity=0.5),), 1)
    assert early.accent([1, 0.5]).notes[0].velocity == 0.5
    with pytest.raises(ValueError, match="complete pairs"):
        Pattern((), 1 + 1e-11).swing()
    # Normal decimal arithmetic still counts as a complete pair grid.
    assert Pattern((), 0.1 + 0.2).swing(step=0.05).beats == 0.1 + 0.2


def test_comparison_preserves_the_backing_and_mix_contract():
    from examples.groove_comparison import comparison_song

    before = comparison_song(developed=False)
    after = comparison_song(developed=True)
    assert (before.bpm, before.seed, before.beats, before.sample_rate) == (
        after.bpm,
        after.seed,
        after.beats,
        after.sample_rate,
    )
    assert before.render_seconds == after.render_seconds
    for original, revised in zip(before.tracks, after.tracks, strict=True):
        assert original.model_dump(exclude={"notes"}) == revised.model_dump(exclude={"notes"})
        if original.name in {"Harmony", "Bass", "Kick"}:
            assert original.notes == revised.notes
        else:
            assert original.notes != revised.notes
