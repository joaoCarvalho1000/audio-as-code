"""Musical mix revisions preserve dynamics, identity, and validated score data."""

import json
import math

import numpy as np
import pytest

from audio_as_code import (
    Automation,
    AutomationPoint,
    Delay,
    MixEdit,
    Note,
    Song,
    TempoChange,
    Track,
    apply_mix,
    audition_song,
    inspect_mix,
    render_audio,
    render_preview_audio,
)
from audio_as_code.cli import main


def lane(parameter="gain", values=(0.2, 0.6), interpolation="linear"):
    return Automation(
        parameter=parameter,
        interpolation=interpolation,
        points=tuple(AutomationPoint(beat=i, value=v) for i, v in enumerate(values)),
    )


def ensemble():
    return Song(
        beats=2,
        sample_rate=22050,
        seed=917,
        master_gain=0.5,
        tempo_map=(TempoChange(beat=1, bpm=90),),
        tracks=(
            Track(
                name="Lead",
                instrument="flute",
                gain=0.3,
                notes=(Note(pitch="C5", start=0, duration=1.5, velocity=0.7),),
            ),
            Track(
                name="Keys",
                instrument="piano",
                gain=0.4,
                pan=-0.1,
                notes=(Note(pitch="E4", start=0, duration=1, velocity=0.4),),
                automation=(lane(), lane("pan", (-0.1, 0.2))),
                effects=(Delay(mix=0.1, repeats=1),),
            ),
            Track(
                name="Bass",
                instrument="bass",
                gain=0.4,
                notes=(Note(pitch="C2", start=0.5, duration=1, velocity=0.6),),
            ),
        ),
    )


def test_group_trim_preserves_envelope_and_all_musical_content():
    song = ensemble()
    original = song.model_dump()
    result = apply_mix(song, [MixEdit(tracks=("Keys", "Bass"), trim_db=-3)])
    scale = 10 ** (-3 / 20)
    assert result.song.tracks[0] == song.tracks[0]
    for before, after in zip(song.tracks[1:], result.song.tracks[1:], strict=True):
        assert after.gain == pytest.approx(before.gain * scale)
        assert after.model_dump(exclude={"gain", "automation"}) == before.model_dump(
            exclude={"gain", "automation"}
        )
    for before, after in zip(
        song.tracks[1].automation[0].points, result.song.tracks[1].automation[0].points, strict=True
    ):
        assert after.beat == before.beat
        assert after.value == pytest.approx(before.value * scale)
    assert result.song.tracks[1].automation[1] == song.tracks[1].automation[1]
    assert result.song.model_dump(exclude={"tracks"}) == song.model_dump(exclude={"tracks"})
    assert result.song.render_seconds == song.render_seconds
    assert song.model_dump() == original
    assert result.report["changes"][0]["before"]["automation"][0]["points"][1]["value"] == 0.6
    json.dumps(result.report, allow_nan=False)


def test_ordered_edits_and_absolute_gain_with_pan():
    song = ensemble()
    result = apply_mix(
        song, [MixEdit(tracks=("Bass",), gain=0.2, pan=0.5), MixEdit(tracks=("Bass",), trim_db=3)]
    )
    assert result.song.tracks[2].gain == pytest.approx(0.2 * 10 ** (3 / 20))
    assert result.song.tracks[2].pan == 0.5
    assert result.report["changes"][0]["after"]["gain"] == 0.2
    assert result.report["changes"][1]["before"]["gain"] == 0.2


@pytest.mark.parametrize("control", [{"gain": 0.3}, {"pan": -0.5}])
def test_absolute_automation_replacement_is_explicit_and_scoped(control):
    song = ensemble()
    with pytest.raises(ValueError, match="has automation"):
        apply_mix(song, [MixEdit(tracks=("Keys",), **control)])
    result = apply_mix(song, [MixEdit(tracks=("Keys",), replace_automation=True, **control)])
    remaining = result.song.tracks[1].automation
    assert len(remaining) == 1
    assert remaining[0].parameter not in control


@pytest.mark.parametrize("interpolation", ["linear", "step"])
def test_master_trim_preserves_tempo_scheduled_automation_and_preview(interpolation):
    song = Song.model_validate(
        {
            **ensemble().model_dump(),
            "automation": [lane("master_gain", interpolation=interpolation)],
        }
    )
    changed = apply_mix(song, [MixEdit(master=True, trim_db=-6)]).song
    before = render_audio(song, normalize=False)
    after = render_audio(changed, normalize=False)
    np.testing.assert_allclose(after.audio, before.audio * 10 ** (-6 / 20), atol=2e-8)
    preview = render_preview_audio(
        changed, start_seconds=0.3, duration_seconds=0.4, normalize=False
    )
    np.testing.assert_array_equal(preview.audio, after.audio[6615:15435])
    assert changed.tracks == song.tracks
    assert changed.automation[0].interpolation == interpolation


def test_audition_mute_wins_and_keeps_tracks_timing_and_seeds():
    song = ensemble()
    audition = audition_song(song, solo=("Keys", "Bass"), mute=("Keys",))
    assert [t.name for t in audition.tracks] == [t.name for t in song.tracks]
    assert audition.tracks[2] == song.tracks[2]
    assert audition.tracks[0].gain == audition.tracks[1].gain == 0
    assert all(p.value == 0 for p in audition.tracks[1].automation[0].points)
    assert audition.tracks[1].automation[1] == song.tracks[1].automation[1]
    for a, b in zip(audition.tracks, song.tracks, strict=True):
        assert a.notes == b.notes and a.effects == b.effects
    assert audition_song(song) == song
    expected = Song.model_validate({**song.model_dump(), "tracks": [song.tracks[2]]})
    np.testing.assert_array_equal(
        render_audio(audition, normalize=False).audio, render_audio(expected, normalize=False).audio
    )
    silent = audition_song(song, mute=tuple(t.name for t in song.tracks))
    assert render_audio(silent).report["audio"]["silent"]
    json.dumps(inspect_mix(silent), allow_nan=False)
    assert inspect_mix(silent)["tracks"][0]["gain_db"] is None


def test_zero_gain_stays_zero_relative_trim_can_boost_within_bounds():
    song = Song(tracks=[Track(name="Silence", gain=0)])
    assert apply_mix(song, [MixEdit(tracks=("Silence",), trim_db=1e308)]).song == song
    changed = apply_mix(
        song, [MixEdit(tracks=("Silence",), gain=0.2), MixEdit(tracks=("Silence",), trim_db=6)]
    ).song
    assert changed.tracks[0].gain == pytest.approx(0.2 * 10 ** (6 / 20))


@pytest.mark.parametrize(
    "edit",
    [
        {},
        {"tracks": ()},
        {"tracks": ("Keys", "Keys"), "gain": 0.2},
        {"tracks": ("Keys",), "master": True, "gain": 0.2},
        {"master": True, "pan": 0},
        {"master": True, "gain": 0.2, "trim_db": -3},
        {"master": True, "gain": -0.1},
        {"master": True, "gain": 1.1},
        {"tracks": ("Keys",), "pan": 1.1},
        {"master": True, "trim_db": math.inf},
        {"master": True, "gain": math.nan},
        {"master": True, "gain": True},
        {"master": True, "trim_db": "-3"},
        {"master": True, "trim_db": -3, "replace_automation": True},
    ],
)
def test_edit_validation(edit):
    with pytest.raises(ValueError):
        MixEdit(**edit)


@pytest.mark.parametrize("names", [("keys",), ("piano",), ("Keys", "Keys"), "Keys", (1,)])
def test_audition_selections_reject_unknown_fuzzy_or_ambiguous_names(names):
    with pytest.raises(ValueError):
        audition_song(ensemble(), solo=names)


def test_exact_case_and_whitespace_track_identity():
    song = Song(tracks=[Track(name="Keys"), Track(name="keys"), Track(name=" Keys ")])
    changed = apply_mix(song, [MixEdit(tracks=("keys",), gain=0.1)]).song
    assert [t.gain for t in changed.tracks] == [0.6, 0.1, 0.6]


@pytest.mark.parametrize(
    "edits, match",
    [
        ([MixEdit(tracks=("piano",), gain=0.2)], "unknown track"),
        ([MixEdit(tracks=("Keys",), trim_db=6)], "exceed gain 1"),
        ([MixEdit(master=True, trim_db=1e308)], "exceed gain 1"),
        ([MixEdit(master=True, trim_db=-1e308)], "underflows"),
    ],
)
def test_invalid_batches_never_mutate_source(edits, match):
    song = ensemble()
    original = song.model_dump()
    with pytest.raises(ValueError, match=match):
        apply_mix(song, [MixEdit(tracks=("Bass",), gain=0.1), *edits])
    assert song.model_dump() == original


def test_revalidates_unsafe_model_copies():
    broken = ensemble().model_copy(update={"master_gain": 2})
    with pytest.raises(ValueError):
        apply_mix(broken, [])
    invalid_edit = MixEdit(master=True, gain=0.1).model_copy(update={"gain": 2})
    with pytest.raises(ValueError):
        apply_mix(ensemble(), [invalid_edit])


def test_dry_group_attenuation_and_pan_measurements():
    song = Song(
        beats=2,
        sample_rate=22050,
        master_gain=1,
        tracks=(
            Track(
                name="Piano",
                instrument="piano",
                gain=0.4,
                notes=(Note(pitch="C4", start=0, duration=1.5),),
            ),
            Track(
                name="Flute",
                instrument="flute",
                gain=0.4,
                notes=(Note(pitch="E5", start=0, duration=1.5),),
            ),
        ),
    )
    before = render_audio(song, normalize=False)
    changed = apply_mix(song, [MixEdit(tracks=("Piano", "Flute"), trim_db=-3)]).song
    after = render_audio(changed, normalize=False)
    np.testing.assert_allclose(after.audio, before.audio * 10 ** (-3 / 20), atol=3e-8)
    assert after.report["audio"]["peak_dbfs"] == pytest.approx(
        before.report["audio"]["peak_dbfs"] - 3, abs=1e-5
    )
    left = apply_mix(song, [MixEdit(tracks=("Piano", "Flute"), pan=-1)]).song
    output = render_audio(left, normalize=False).audio
    assert np.max(np.abs(output[:, 0])) > 0
    assert np.max(np.abs(output[:, 1])) == 0


def test_cli_json_batch_report_audition_and_inspection(tmp_path, capsys):
    score, edits, revised, report = [
        tmp_path / p for p in ("input score.json", "edits.json", "new score.json", "report.json")
    ]
    ensemble().save(score)
    edits.write_text(json.dumps([{"tracks": ["Keys", "Bass"], "trim_db": -3}]), encoding="utf-8")
    assert main(["mix", str(score)]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "score_mix_settings"
    assert (
        main(
            [
                "mix",
                str(score),
                "--edits",
                str(edits),
                "-o",
                str(revised),
                "--solo",
                "Bass",
                "--report",
                str(report),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result == json.loads(report.read_text(encoding="utf-8"))
    assert len(result["changes"]) == 2
    assert Song.load(revised).tracks[0].gain == 0
    assert result["after"] == inspect_mix(Song.load(revised))


@pytest.mark.parametrize(
    "failure",
    [
        "late_invalid",
        "alias",
        "report_alias",
        "invalid_json_edit",
        "missing_output",
        "invalid_solo",
    ],
)
def test_cli_preflight_and_batch_errors_preserve_files(tmp_path, capsys, failure):
    score, output, edits, report = [
        tmp_path / p for p in ("score.json", "new.json", "edits.json", "report.json")
    ]
    ensemble().save(score)
    output.write_text("preserve output", encoding="utf-8")
    report.write_text("preserve report", encoding="utf-8")
    payload = [{"tracks": ["Bass"], "trim_db": -3}]
    if failure == "late_invalid":
        payload.append({"tracks": ["Unknown"], "gain": 0.2})
    if failure == "invalid_json_edit":
        payload.append({"master": True, "gain": 2})
    edits.write_text(json.dumps(payload), encoding="utf-8")
    original = score.read_bytes()
    args = [
        "mix",
        str(score),
        "--edits",
        str(edits),
        "--report",
        str(score if failure == "report_alias" else report),
    ]
    if failure != "missing_output":
        args.extend(["-o", str(edits if failure == "alias" else output)])
    if failure == "invalid_solo":
        args.extend(["--solo", "Unknown"])
    assert main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    diagnostic = json.loads(captured.err)
    assert diagnostic["error"] == (
        "invalid_mix_edits" if failure == "invalid_json_edit" else "operation_failed"
    )
    if failure == "invalid_json_edit":
        assert diagnostic["issues"][0]["path"] == ["edits", 1, "gain"]
    assert score.read_bytes() == original
    assert output.read_text(encoding="utf-8") == "preserve output"
    assert report.read_text(encoding="utf-8") == "preserve report"


def test_cli_reports_multiple_bad_edit_locations_without_writing(tmp_path, capsys):
    score, edits, output = [tmp_path / name for name in ("score.json", "edits.json", "new.json")]
    ensemble().save(score)
    edits.write_text(
        json.dumps([{"tracks": ["Bass"], "pan": 2}, {"master": True, "gain": "loud"}]),
        encoding="utf-8",
    )
    assert main(["mix", str(score), "--edits", str(edits), "-o", str(output)]) == 2
    captured = capsys.readouterr()
    diagnostic = json.loads(captured.err)
    assert not captured.out and not output.exists()
    assert diagnostic["error"] == "invalid_mix_edits"
    assert [issue["path"] for issue in diagnostic["issues"]] == [
        ["edits", 0, "pan"],
        ["edits", 1, "gain"],
    ]
