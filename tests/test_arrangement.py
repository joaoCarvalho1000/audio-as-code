"""Timestamp cues, scoped revisions, and measured loop previews."""

import numpy as np
import pytest

from audio_as_code.arrangement import (
    Arrangement,
    LoopRegion,
    Section,
    beat_at_seconds,
    place_at_seconds,
    render_loop_preview,
)
from audio_as_code.model import Note, Song, TempoChange, Track
from audio_as_code.pattern import Pattern
from audio_as_code.render import render_audio


def _song() -> Song:
    return Song(
        title="Sections",
        bpm=120,
        beats=12,
        seed=23,
        tempo_map=(TempoChange(beat=4, bpm=60), TempoChange(beat=8, bpm=150)),
        tracks=(
            Track(
                name="Lead",
                instrument="pluck",
                notes=(
                    Note(pitch="C4", start=0, duration=1),
                    Note(pitch="D4", start=4, duration=1),
                    Note(pitch="E4", start=8, duration=1),
                ),
            ),
            Track(name="Bass", instrument="bass", notes=(Note(pitch="C2", start=5),)),
        ),
    )


def test_cue_inverse_and_rendered_hit_across_tempo_changes():
    source = _song()
    # Beat 6 is four seconds: first four beats at 120, then two at 60.
    assert beat_at_seconds(source, 4) == 6
    assert beat_at_seconds(source, source.beat_to_seconds(9)) == pytest.approx(9)
    hit = Pattern.sequence(["G4"], step=0.25, gate=1)
    notes = place_at_seconds(source, hit, 4.25)
    assert notes[0].start == pytest.approx(6.25)
    assert source.beat_to_seconds(notes[0].start) == pytest.approx(4.25)
    song = Song.model_validate(
        {**source.model_dump(), "tracks": [Track(name="Hit", notes=notes).model_dump()]}
    )
    audio = render_audio(song, normalize=False).audio
    start = round(4.25 * song.sample_rate)
    assert np.max(np.abs(audio[:start])) == 0
    assert np.max(np.abs(audio[start : start + 256])) > 0


def test_section_replacement_preserves_other_material_and_timing():
    source = _song()
    arrangement = Arrangement(source, (Section("intro", 0, 4), Section("middle", 4, 8)))
    replacement = Pattern.sequence(["A4", None, "B4", None], gate=0.5)
    revised = arrangement.replace_section("middle", {"Lead": replacement})
    assert revised.song.seed == source.seed
    assert revised.song.tempo_map == source.tempo_map
    assert revised.song.tracks[1] is source.tracks[1]
    assert revised.sections == arrangement.sections
    assert revised.song.tracks[0].notes[0] == source.tracks[0].notes[0]
    assert revised.song.tracks[0].notes[-1] == source.tracks[0].notes[-1]
    assert [(n.pitch, n.start) for n in revised.song.tracks[0].notes] == [
        ("C4", 0),
        ("A4", 4),
        ("B4", 6),
        ("E4", 8),
    ]
    assert source.tracks[0].notes[1].pitch == "D4"
    assert source.beat_to_seconds(revised.section("middle").start_beat) == 2
    assert source.beat_to_seconds(revised.section("middle").end_beat) == 6


@pytest.mark.parametrize("value", [-1, True, "4", float("nan"), float("inf")])
def test_invalid_cue_times(value):
    with pytest.raises(ValueError):
        beat_at_seconds(_song(), value)


def test_section_validation_and_crossing_notes():
    song = _song()
    with pytest.raises(ValueError, match="overlap"):
        Arrangement(song, (Section("one", 0, 5), Section("two", 4, 8)))
    with pytest.raises(ValueError, match="unique"):
        Arrangement(song, (Section("one", 0, 4), Section("one", 4, 8)))
    with pytest.raises(ValueError, match="beyond"):
        Arrangement(song, (Section("out", 11, 13),))
    arrangement = Arrangement(song, (Section("middle", 4, 8),))
    with pytest.raises(ValueError, match="length"):
        arrangement.replace_section("middle", {"Lead": Pattern.sequence(["C4"])})
    with pytest.raises(ValueError, match="unknown tracks"):
        arrangement.replace_section("middle", {"No track": Pattern((), 4)})
    crossing = Song.model_validate(
        {
            **song.model_dump(),
            "tracks": [
                Track(name="Lead", notes=(Note(start=3, duration=2),)).model_dump(),
                song.tracks[1].model_dump(),
            ],
        }
    )
    with pytest.raises(ValueError, match="crossing section start"):
        Arrangement(crossing, (Section("middle", 4, 8),)).replace_section(
            "middle", {"Lead": Pattern((), 4)}
        )


def test_loop_preview_repeats_actual_frames_and_reports_boundary():
    song = Song(
        bpm=120,
        beats=4,
        sample_rate=22050,
        tracks=(Track(name="Lead", notes=(Note(duration=0.5),)),),
    )
    region = LoopRegion(0, 4)
    preview = render_loop_preview(song, region, repetitions=2)
    details = preview.report["loop"]
    assert details["cycle_frames"] == round(song.seconds * song.sample_rate)
    assert details["preview_frames"] == 2 * details["cycle_frames"]
    assert details["estimated_tail_past_end_seconds"] == 0
    assert np.array_equal(
        preview.audio[: details["cycle_frames"]], preview.audio[details["cycle_frames"] :]
    )
    assert details["boundary_jump"] == pytest.approx(
        float(np.max(np.abs(preview.audio[0] - preview.audio[details["cycle_frames"] - 1])))
    )


def test_loop_requires_explicit_tail_crop_and_rejects_invalid_bounds():
    song = Song(
        beats=2,
        tracks=(Track(name="Pad", notes=(Note(start=1.5, duration=0.5),), release_seconds=0.3),),
    )
    with pytest.raises(ValueError, match="tail"):
        render_loop_preview(song, LoopRegion(0, 2))
    cropped = render_loop_preview(song, LoopRegion(0, 2), allow_tail_crop=True)
    assert cropped.report["loop"]["estimated_tail_past_end_seconds"] == pytest.approx(0.3)
    with pytest.raises(ValueError, match="beyond"):
        render_loop_preview(song, LoopRegion(0, 3))
    with pytest.raises(ValueError, match="positive"):
        LoopRegion(0, 0)
