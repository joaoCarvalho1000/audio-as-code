"""Musical transformations compile to ordinary immutable score notes."""

import pytest

from audio_as_code import Note, Pattern, Song, Track


def test_overlay_preserves_rests_order_duplicates_and_inputs():
    base = Pattern.sequence(["C4", None], gate=1)
    layer = Pattern.sequence(["E4", None, None], gate=1)

    combined = base.overlay(layer, offset=1)

    assert combined.beats == 4
    assert [(n.pitch, n.start, n.duration) for n in combined.notes] == [
        ("C4", 0, 1),
        ("E4", 1, 1),
    ]
    assert base.beats == 2
    assert layer.notes[0].start == 0
    assert base.overlay(base).notes == base.notes + base.notes
    assert layer.overlay(base).beats == 3
    # Appending starts after the layer's trailing silence, not after its last note.
    assert combined.then(base).notes[-1].start == 4


def test_overlay_with_silence_extends_declared_length():
    phrase = Pattern.sequence(["C4"], gate=1)
    silence = Pattern.sequence([None, None])
    result = phrase.overlay(silence, offset=3)
    assert result.notes == phrase.notes
    assert result.beats == 5
    assert silence.overlay(silence, offset=1) == Pattern((), 3)


def test_stretch_scales_chords_rests_and_exact_note_boundaries():
    phrase = Pattern.sequence([None, ["C4", "E4"], "G4", None], step=0.5, gate=1)

    stretched = phrase.stretch(2)

    assert stretched.beats == 4
    assert [n.start for n in stretched.notes] == [1, 1, 2]
    assert [n.duration for n in stretched.notes] == [1, 1, 1]
    assert stretched.stretch(0.5) == phrase
    assert Pattern.sequence(["C4"], gate=1).stretch(3).notes[0].duration == 3
    assert Pattern((), 2).stretch(0.25) == Pattern((), 0.5)


def test_transformations_preserve_unrelated_note_controls():
    note = Note(pitch="Bb3", start=0.5, duration=0.25, velocity=0.4, release_seconds=0.7)
    phrase = Pattern((note,), 2)
    transformed = phrase.stretch(2).scale_velocity(1.5)

    assert transformed.notes[0].model_dump() == {
        **note.model_dump(),
        "start": 1,
        "duration": 0.5,
        "velocity": pytest.approx(0.6),
    }
    assert phrase.notes == (note,)
    assert transformed.overlay(phrase, offset=4).notes[-1].release_seconds == 0.7


def test_scale_velocity_preserves_accents_and_rejects_clipping():
    phrase = Pattern((Note(velocity=0.25), Note(pitch="E4", velocity=0.5)), 2)
    louder = phrase.scale_velocity(2)
    assert [n.velocity for n in louder.notes] == [0.5, 1]
    assert louder.beats == phrase.beats
    assert louder.scale_velocity(0.5) == phrase
    with pytest.raises(ValueError):
        phrase.scale_velocity(2.01)
    assert Pattern((), 2).scale_velocity(3) == Pattern((), 2)


def test_composition_compiles_to_existing_score_json():
    motif = Pattern.sequence(["C4", None, "G4", None], step=0.5, gate=1, velocity=0.5)
    answer = motif.transpose(12).stretch(0.5).scale_velocity(0.6)
    phrase = motif.overlay(answer, offset=1).repeat(2)
    song = Song(
        title="Call and answer",
        beats=phrase.beats,
        tracks=(Track(name="Plucked duet", instrument="pluck", notes=phrase.at(0)),),
    )
    assert song.beats == 4
    assert [(n.pitch, n.start) for n in song.tracks[0].notes] == [
        ("C4", 0),
        ("G4", 1),
        (72, 1),
        (79, 1.5),
        ("C4", 2),
        ("G4", 3),
        (72, 3),
        (79, 3.5),
    ]
    assert Song.model_validate_json(song.model_dump_json()) == song


@pytest.mark.parametrize("factor", [0, -1, True, False, "2", None, float("nan"), float("inf")])
@pytest.mark.parametrize("method", ["stretch", "scale_velocity"])
def test_factors_are_validated_even_for_silent_patterns(method, factor):
    with pytest.raises(ValueError, match="factor"):
        getattr(Pattern((), 2), method)(factor)


@pytest.mark.parametrize("offset", [-1, True, "0", None, float("nan"), float("inf")])
def test_overlay_rejects_invalid_offsets_even_for_silence(offset):
    with pytest.raises(ValueError, match="offset"):
        Pattern((), 1).overlay(Pattern((), 1), offset=offset)


@pytest.mark.parametrize("other", [None, (), "C4", 1])
@pytest.mark.parametrize("method", ["then", "overlay"])
def test_combining_requires_another_pattern(method, other):
    with pytest.raises(ValueError, match="other must be a Pattern"):
        getattr(Pattern((), 1), method)(other)


@pytest.mark.parametrize(
    "steps", [None, 42, 1.5, "C4", b"C4", bytearray(b"C4"), {60}, {0: 60}, iter([60]), []]
)
def test_sequence_rejects_invalid_outer_containers(steps):
    with pytest.raises(ValueError, match="steps"):
        Pattern.sequence(steps)


@pytest.mark.parametrize("item", [1.5, b"C4", bytearray(b"C4"), {60}, {0: 60}, iter([60])])
def test_sequence_rejects_invalid_step_containers(item):
    with pytest.raises(ValueError, match="each step"):
        Pattern.sequence([item])


def test_empty_chords_remain_rests_and_invalid_chord_pitches_are_rejected():
    assert Pattern.sequence([[], (), None]) == Pattern((), 3)
    for item in (True, [None], ["H4"], [[60]], [128]):
        with pytest.raises(ValueError):
            Pattern.sequence([item])


def test_overflow_and_underflow_do_not_create_invalid_transformed_notes():
    phrase = Pattern((Note(start=1, duration=1, velocity=0.5),), 2)
    for method, factor in (("stretch", 1e308), ("scale_velocity", 1e-323)):
        # Multiplication either overflows the phrase length or underflows velocity.
        target = phrase if method == "stretch" else phrase.scale_velocity(0.1)
        with pytest.raises(ValueError):
            getattr(target, method)(factor)
    with pytest.raises(ValueError):
        Pattern((), 1e308).overlay(Pattern((), 1e308), offset=1e308)
