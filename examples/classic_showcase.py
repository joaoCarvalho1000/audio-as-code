"""Five complete public-domain scores rendered entirely from procedural instruments.

Run: uv run python examples/classic_showcase.py --ffmpeg ffmpeg
No source audio or online download is used. See docs/classic-showcase.md.
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
import shutil
import subprocess
import zipfile
from collections import Counter
from functools import lru_cache
from pathlib import Path

from audio_as_code import Note, Song, Track, export_midi, render


@lru_cache(maxsize=1)
def pieces() -> dict:
    return json.loads(
        Path(__file__).with_name("music").joinpath("classics-full.json").read_text(encoding="utf-8")
    )


# Source parts, voice, octave transposition, gain, pan. Source pitches/onsets
# remain unchanged; all classic arrangements keep the source register.
PLANS = {
    "fur_elise": [(("right",), "piano", 0, 1.0, 0.04), (("left",), "piano", 0, 0.70, -0.16)],
    "cello_prelude": [(("cello",), "cello", 0, 0.88, 0)],
    "turkish_march": [(("right",), "piano", 0, 1.0, 0.04), (("left",), "piano", 0, 0.70, -0.16)],
    "greensleeves": [
        (("melody",), "guitar", 0, 0.90, 0.04),
        (("harmony",), "guitar", 0, 0.68, -0.12),
    ],
    "ode_to_joy": [
        (("soprano",), "organ", 0, 0.30, -0.12),
        (("alto",), "organ", 0, 0.18, 0.18),
        (("tenor",), "organ", 0, 0.18, -0.25),
        (("bass",), "organ", 0, 0.22, 0.10),
    ],
}
DESCRIPTIONS = {
    "fur_elise": (
        "The complete piano work, including both printed opening repeats and all episodes."
    ),
    "cello_prelude": (
        "The complete Prelude, from opening arpeggios to the final chord, on solo cello."
    ),
    "turkish_march": (
        "The complete piano rondo, including every printed repeat, alternative and coda."
    ),
    "greensleeves": "The complete two-voice source arrangement on procedural guitar.",
    "ode_to_joy": "The complete sixteen-bar SATB hymn arrangement, voiced instrumentally on organ.",
}


def _arrange(key: str, seed: int, *, bpm: float | None = None) -> Song:
    piece = pieces()[key]
    end = piece["beats"] + 0.75
    tracks = []
    for parts, voice, transpose, gain, pan in PLANS[key]:
        rows = [row for part in parts for row in piece["parts"][part]]
        tracks.append(
            Track(
                name=" + ".join(parts).title(),
                instrument=voice,
                gain=gain,
                pan=pan,
                release_seconds=0.10 if voice in {"piano", "guitar"} else 0.04,
                notes=[
                    Note(pitch=pitch + transpose, start=start, duration=duration, velocity=velocity)
                    for pitch, start, duration, velocity in rows
                ],
            )
        )
    return Song(
        title=piece["title"],
        bpm=bpm or piece["bpm"],
        beats=end,
        sample_rate=44100,
        seed=seed,
        master_gain=1.0 if key in {"fur_elise", "turkish_march", "greensleeves"} else 0.85,
        tracks=tracks,
    )


def fur_elise() -> Song:
    """Complete WoO 59, both opening repeats unfolded; piano at 72 BPM."""
    return _arrange("fur_elise", 2701)


def cello_prelude() -> Song:
    """Complete BWV 1007 Prelude, 42 bars; solo cello at source tempo 80 BPM."""
    return _arrange("cello_prelude", 2702)


def turkish_march() -> Song:
    """Complete K.331 rondo with all printed repeats; piano at 112 BPM."""
    return _arrange("turkish_march", 2703)


def greensleeves() -> Song:
    """Complete Fontaine guitar arrangement, both strains and returns; 100 BPM."""
    return _arrange("greensleeves", 2704)


def ode_to_joy() -> Song:
    """Complete Chubb SATB hymn on organ at 100 BPM; no vocal synthesis."""
    return _arrange("ode_to_joy", 2705)


BUILDERS = {
    "classic-fur-elise": fur_elise,
    "classic-cello-prelude": cello_prelude,
    "classic-turkish-march": turkish_march,
    "classic-greensleeves": greensleeves,
    "classic-ode-to-joy": ode_to_joy,
}


def _verify_source(song: Song, key: str) -> list[dict]:
    """Check every emitted pitch, onset, gate and velocity against the full source data."""
    mappings = []
    for track, plan in zip(song.tracks, PLANS[key], strict=True):
        parts, voice, transpose, _gain, _pan = plan
        rows = [row for part in parts for row in pieces()[key]["parts"][part]]
        expected = Counter((p + transpose, s, d, v) for p, s, d, v in rows)
        actual = Counter((n.pitch, n.start, n.duration, n.velocity) for n in track.notes)
        if expected != actual:
            raise RuntimeError(f"Source pitch/onset mismatch: {key}, {track.name}")
        mappings.append(
            {
                "track": track.name,
                "source_parts": list(parts),
                "instrument": voice,
                "transpose_semitones": transpose,
                "source_events": len(rows),
                "arranged_events": len(track.notes),
            }
        )
    return mappings


def _copy_source(destination: Path) -> None:
    source = Path(__file__).resolve()
    importer = source.with_name("music") / "build_classics_full.py"
    dataset = source.with_name("music") / "classics-full.json"
    for origin, target in [
        (source, destination / source.name),
        (importer, destination / "music" / importer.name),
        (dataset, destination / "music" / "classics-full.json"),
    ]:
        target.parent.mkdir(parents=True, exist_ok=True)
        if origin != target.resolve():
            shutil.copyfile(origin, target)
    root = source.parent.parent
    # This is a complete local engine+recipe bundle, not a script with hidden data dependencies.
    if not (root / "src/audio_as_code").is_dir():
        raise ValueError("Build source bundles from the repository's examples/classic_showcase.py")
    bundle = destination / "classic-showcase-source.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in [
            source,
            importer,
            dataset,
            *sorted(source.with_name("music").joinpath("classics-sources").glob("*")),
            root / "pyproject.toml",
            root / "uv.lock",
            root / "LICENSE",
            root / "README.md",
            root / "docs/classic-showcase.md",
            *sorted((root / "src/audio_as_code").glob("*.py")),
            *sorted((root / "src/audio_as_code/_project_templates").glob("*.txt")),
            root / "src/audio_as_code/_project_templates/score.json",
            root / "src/audio_as_code/py.typed",
        ]:
            archive.write(path, "audio-as-code-classics/" + path.relative_to(root).as_posix())


def export_all(destination: str | Path, *, ffmpeg: str | Path | None = None) -> list[dict]:
    encoder = str(ffmpeg) if ffmpeg else shutil.which("ffmpeg")
    if not encoder:
        raise ValueError("FFmpeg is required for MP3 previews; supply --ffmpeg PATH")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "manifest.json").unlink(missing_ok=True)
    _copy_source(destination)
    exported = []
    for piece_id, builder in BUILDERS.items():
        key = builder.__name__
        source = pieces()[key]
        song = builder()
        mappings = _verify_source(song, key)
        song.save(destination / f"{piece_id}.json")
        if Song.load(destination / f"{piece_id}.json") != song:
            raise RuntimeError(f"Score round-trip failed: {piece_id}")
        midi = export_midi(song, destination / f"{piece_id}.mid")
        print(f"Rendering {piece_id} ({song.seconds:.2f}s)", flush=True)
        report = render(song, destination / f"{piece_id}.wav", normalize=False)
        if (
            report["wav"]["silent"]
            or report["wav"]["full_scale_samples"]
            or not all(math.isfinite(report["audio"][k]) for k in ("peak", "rms"))
            or not 30 <= report["audio"]["duration_seconds"] <= 300
        ):
            raise RuntimeError(
                f"Silent, clipped, non-finite or incorrectly timed render: {piece_id}"
            )
        report.update(midi=midi, source_mapping=mappings)
        (destination / f"{piece_id}.report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        subprocess.run(
            [
                encoder,
                "-v",
                "error",
                "-y",
                "-i",
                str(destination / f"{piece_id}.wav"),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(destination / f"{piece_id}.mp3"),
            ],
            check=True,
        )
        sections = [
            *source["sections"],
            {"name": "Ring-out", "start_beat": source["beats"], "end_beat": song.beats},
        ]
        exported.append(
            {
                "id": piece_id,
                "title": song.title,
                "description": DESCRIPTIONS[key],
                "bpm": song.bpm,
                "beats": song.beats,
                "duration_seconds": song.seconds,
                "instruments": list(dict.fromkeys(t.instrument for t in song.tracks)),
                "sections": sections,
                "wav": f"{piece_id}.wav",
                "midi": f"{piece_id}.mid",
                "score": f"{piece_id}.json",
                "preview": f"{piece_id}.mp3",
                "report": f"{piece_id}.report.json",
                "source": "classic_showcase.py",
                "source_bundle": "classic-showcase-source.zip",
                "source_dependencies": ["music/classics-full.json"],
                "source_dataset": "music/classics-full.json",
                "source_function": builder.__name__,
                "code_excerpt": inspect.getsource(builder).strip(),
                "seed": song.seed,
                "sample_rate": song.sample_rate,
                "tracks": len(song.tracks),
                "notes": sum(len(t.notes) for t in song.tracks),
                "levels": report["wav"],
                "warnings": report["warnings"],
                "composer": source["composer"],
                "source_url": source["source_url"],
                "edition_credit": source["credit"],
                "source_license": source["license"],
                "excerpt": False,
                "complete": True,
                "pair_id": piece_id,
                "variant": "classic",
                "work_title": source["title"],
                "performance_scope": source["scope"],
                "source_midi_beats": source["source_midi_beats"],
                "source_midi_notes": source["source_midi_notes"],
                "repeat_policy": source["repeat_policy"],
                "repeat_expansion": source["repeat_expansion"],
                "arrangement": DESCRIPTIONS[key],
                "source_piece": key,
                "source_beats": source["beats"],
                "source_bpm": source["bpm"],
                "source_mapping": mappings,
                "source_verified_date": "2026-10-02",
                "arrangement_notes": (
                    "Complete source pitches, performed onsets, written gates and MIDI velocities "
                    "retained; no register shifts. "
                    "Printed repeats explicitly unfolded from notation. "
                    "Piano/cello/guitar match source instrument families; SATB hymn is voiced on "
                    "organ, without vocals. Short renderer releases add natural ending space; "
                    "no delay/reverb. These scores use no pedal events; "
                    "detailed acoustic articulation is not modeled."
                ),
            }
        )
    (destination / "manifest.json").write_text(
        json.dumps({"pieces": exported}, indent=2) + "\n", encoding="utf-8"
    )
    return exported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="output/classic-showcase")
    parser.add_argument("--ffmpeg", help="Installed FFmpeg executable for 192 kbps MP3 previews")
    args = parser.parse_args()
    export_all(args.output, ffmpeg=args.ffmpeg)
