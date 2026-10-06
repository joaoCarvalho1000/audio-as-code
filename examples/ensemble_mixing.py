"""An original ensemble, precise mix revisions, selected auditions and measured previews."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from audio_as_code import (
    Automation,
    AutomationPoint,
    MixEdit,
    Pattern,
    Song,
    Track,
    apply_mix,
    audition_song,
    inspect_mix,
    render,
    render_preview,
)


def ensemble_song() -> Song:
    """Eight beats of procedural chamber pop; the accompaniment swells gently."""
    return Song(
        title="Room for the melody",
        bpm=112,
        beats=8,
        seed=42,
        master_gain=0.7,
        tracks=(
            Track(
                name="Lead",
                instrument="flute",
                gain=0.5,
                notes=Pattern.sequence(
                    ["E5", "G5", "A5", "G5", "E5", "D5", "C5", None],
                    gate=0.75,
                    velocity=0.7,
                ).notes,
            ),
            Track(
                name="Keys",
                instrument="piano",
                gain=0.45,
                notes=Pattern.sequence(
                    ["C4", "E4", "G4", "E4", "F4", "A4", "G4", "C4"],
                    gate=0.7,
                    velocity=0.6,
                ).notes,
                automation=(
                    Automation(
                        parameter="gain",
                        points=(
                            AutomationPoint(beat=0, value=0.3),
                            AutomationPoint(beat=4, value=0.5),
                            AutomationPoint(beat=8, value=0.35),
                        ),
                    ),
                ),
            ),
            Track(
                name="Guitar",
                instrument="guitar",
                gain=0.4,
                notes=Pattern.sequence(
                    ["G3", None, "E4", None, "A3", None, "G3", None],
                    gate=0.6,
                    velocity=0.65,
                ).notes,
            ),
            Track(
                name="Bass",
                instrument="bass_guitar",
                gain=0.4,
                notes=Pattern.sequence(
                    ["C2", "G2", "F2", "G2"], step=2, gate=0.7, velocity=0.65
                ).notes,
            ),
            Track(
                name="Pulse",
                instrument="hat",
                gain=0.2,
                notes=Pattern.sequence(["C4"] * 16, step=0.5, gate=0.2, velocity=0.4).notes,
            ),
        ),
    )


def headroom(report: dict) -> dict:
    """Summarize actual rendered samples; null headroom denotes an entirely silent mix."""
    return {
        "before_output_gain_peak_dbfs": report["before_gain"]["peak_dbfs"],
        "output_gain_db": 20 * math.log10(report["gain_applied"]),
        "output_sample_headroom_db": -report["audio"]["peak_dbfs"]
        if report["audio"]["peak_dbfs"] is not None
        else None,
        "clipped_samples": report["audio"]["clipped_samples"],
        "warnings": report["warnings"],
    }


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/agent-mixing-controls")
    output.mkdir(parents=True, exist_ok=True)
    original = ensemble_song()
    # Groups are exact names in composer code, not a second bus state in score JSON.
    accompaniment = ("Keys", "Guitar")
    edits = [
        MixEdit(tracks=accompaniment, trim_db=-3),  # Preserve the piano swell.
        MixEdit(tracks=("Keys",), pan=-0.35),
        MixEdit(tracks=("Guitar",), pan=0.35),
        MixEdit(tracks=("Bass", "Pulse"), trim_db=-1.5),
        MixEdit(tracks=("Lead",), gain=0.55),  # Explicit absolute linear level.
        MixEdit(master=True, trim_db=-1),
    ]
    revision = apply_mix(original, edits)
    original.save(output / "before.json")
    revision.song.save(output / "after.json")
    (output / "edits.json").write_text(
        json.dumps([e.model_dump(mode="json", exclude_none=True) for e in edits], indent=2),
        encoding="utf-8",
    )
    # Shared-gain stems use the full mix's output gain; none is normalized separately.
    before = render(original, output / "before.wav", wav_format="pcm24")
    after = render(
        revision.song, output / "after.wav", wav_format="pcm24", stems_dir=output / "stems"
    )
    selected = audition_song(revision.song, solo=("Lead", "Keys", "Guitar"), mute=("Guitar",))
    selected.save(output / "audition.json")
    audition = render(selected, output / "audition.wav", normalize=False, wav_format="float32")
    preview = render_preview(
        revision.song,
        output / "preview.wav",
        start_seconds=1,
        duration_seconds=2,
        wav_format="pcm24",
    )
    report = {
        "settings": inspect_mix(original),
        "revision": revision.report,
        "rendered": {"before": before, "after": after, "audition": audition, "preview": preview},
        "headroom": {"before": headroom(before), "after": headroom(after)},
        "audition_selection": {"solo": ["Lead", "Keys", "Guitar"], "mute": ["Guitar"]},
        "notes": [
            "Settings describe score controls; measurements describe rendered samples.",
            "Solo/mute creates a disposable score; keep after.json to restore the mix.",
            "Preview costs a complete render and preserves its master output gain.",
            "Peak and RMS cannot establish perceived balance or instrumental realism.",
        ],
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Ensemble mix review</title>'
        "<body><h1>Room for the melody</h1><p>Procedural voices. Compare at one player volume; "
        "each render report states its output gain. No perceptual judgment is inferred.</p>"
        + "".join(
            f'<h2>{label}</h2><audio controls src="{name}.wav"></audio>'
            for name, label in (
                ("before", "Before"),
                ("after", "Revised ensemble"),
                ("audition", "Lead and keys audition"),
                ("preview", "Revised two-second excerpt"),
            )
        )
        + '<p><a href="report.json">Settings, revisions and measured headroom</a></p>'
        "</body></html>",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "headroom": report["headroom"]}, indent=2))


if __name__ == "__main__":
    main()
