"""Original video/game/presentation briefs using only the documented public API."""

import argparse
import hashlib
import json
import platform
import shutil
import sys
import wave
from pathlib import Path

import mido
import numpy as np

from audio_as_code import (
    Note,
    Song,
    Track,
    analyze_wav,
    export_midi,
    inspect_score,
    render,
    render_audio,
)

BRIEFS = {
    "video": {
        "request": "30-second warm, playful video music; clear reveal at 20s and settled ending.",
        "revision": "Keep the melody, harmony, cue and duration; make the drums softer.",
        "sections": [
            ("statement", 0, 10),
            ("answer", 10, 20),
            ("reveal", 20, 27.5),
            ("cadence", 27.5, 30),
        ],
    },
    "game": {
        "request": "A seamless 12-second exploration loop with a small hint of danger.",
        "revision": "Reduce the tension; keep the motif, harmony, bass, tempo and loop length.",
        "sections": [("four-bar loop", 0, 12)],
    },
    "presentation": {
        "request": "A bright presentation identity sting with an exact nine-second ending.",
        "revision": "Make it more triumphant without changing the identity melody or duration.",
        "sections": [("identity", 0, 2), ("lift", 2, 5), ("dominant", 5, 7), ("resolution", 7, 9)],
    },
}


def notes(pitches, start, duration, velocity=0.6):
    return [Note(pitch=p, start=start, duration=duration, velocity=velocity) for p in pitches]


def video():
    """Twelve bars at 96 BPM; reveal on bar nine = exactly 20 seconds."""
    melody, chords, bass, kick, hat = [], [], [], [], []
    progression = [([60, 64, 67], 36), ([57, 60, 64], 33), ([57, 60, 65], 41), ([59, 62, 67], 43)]
    motif = [(0, 72, 0.6), (0.75, 76, 0.35), (1.5, 79, 0.65), (3, 76, 0.7)]
    for bar in range(11):
        start = bar * 4
        chord, root = progression[bar % 4]
        chords += notes(chord, start, 3.65, 0.42)
        bass += notes([root], start, 1.7, 0.65) + notes([root + 7], start + 2, 1.5, 0.5)
        # A small answer follows each statement, and the reveal raises the motif.
        for offset, pitch, duration in motif:
            shift = 12 if bar == 8 else (-2 if bar % 4 == 3 else 0)
            melody += notes([pitch + shift], start + offset, duration, 0.64)
        for beat in (0, 2):
            kick += notes([36], start + beat, 0.22, 0.48)
        for beat in (0.5, 1.5, 2.5, 3.5):
            hat += notes([42], start + beat, 0.1, 0.25)
    # Dominant in bar eleven resolves into a sustained tonic with room to settle.
    chords[-3:] = notes([59, 62, 67], 40, 3.65, 0.42)
    chords += notes([60, 64, 67], 44, 3.65, 0.4)
    bass += notes([36], 44, 3.6, 0.58)
    melody += notes([72], 44, 3.6, 0.55)
    return Song(
        title="Pocket sunshine",
        bpm=96,
        beats=48,
        seed=8201,
        master_gain=0.7,
        tracks=[
            Track(name="Melody", instrument="marimba", gain=0.48, pan=0.18, notes=melody),
            Track(name="Harmony", instrument="electric_piano", gain=0.27, pan=-0.22, notes=chords),
            Track(name="Bass", instrument="bass", gain=0.31, notes=bass),
            Track(name="Kick", instrument="kick", gain=0.2, notes=kick),
            Track(name="Hat", instrument="hat", gain=0.1, pan=0.25, notes=hat),
            Track(
                name="Reveal",
                instrument="celesta",
                gain=0.45,
                pan=-0.1,
                notes=notes([79, 84], 32, 1.5, 0.72),
            ),
        ],
    )


def game():
    """Four bars at 80 BPM, a sparse articulated exploration loop."""
    melody, harmony, bass = [], [], []
    roots = [45, 41, 48, 43]
    voicings = [[60, 64, 69], [60, 65, 69], [60, 64, 67], [59, 62, 67]]
    phrase = [69, 72, 76, 72, 69, 67, 64, 67]
    for bar in range(4):
        start = bar * 4
        harmony += notes(voicings[bar], start, 3.92, 0.38)
        for offset in (0, 2):
            bass += notes([roots[bar]], start + offset, 1.85, 0.5)
        for step in range(2):
            melody += notes([phrase[bar * 2 + step]], start + step * 2, 1.92, 0.52)
    return Song(
        title="Small lantern patrol",
        bpm=80,
        beats=16,
        seed=8202,
        master_gain=0.65,
        tracks=[
            Track(name="Motif", instrument="marimba", gain=0.42, pan=0.2, notes=melody),
            Track(name="Harmony", instrument="electric_piano", gain=0.27, pan=-0.2, notes=harmony),
            Track(name="Bass", instrument="bass", gain=0.25, notes=bass),
            Track(
                name="Tension",
                instrument="triangle",
                gain=0.13,
                pan=-0.1,
                notes=notes([71], 10, 1.85, 0.4) + notes([68], 14, 1.85, 0.4),
            ),
        ],
    )


def presentation():
    """A nine-second identity phrase with a resolved final chord."""
    lead = []
    for start, pitch, length in [
        (0, 67, 0.6),
        (0.75, 72, 0.6),
        (1.5, 76, 1.2),
        (4, 74, 0.7),
        (5, 77, 0.7),
        (6, 79, 1.5),
        (10, 79, 0.7),
        (11, 83, 0.7),
        (12, 86, 1.5),
        (14, 84, 3.8),
    ]:
        lead += notes([pitch], start, length, 0.65)
    harmony = (
        notes([60, 64, 67], 0, 3.5, 0.45)
        + notes([60, 65, 69], 4, 5.5, 0.45)
        + notes([59, 62, 67], 10, 3.5, 0.52)
        + notes([60, 64, 67], 14, 3.8, 0.58)
    )
    bass = notes([36], 0, 3.5) + notes([41], 4, 5.5) + notes([43], 10, 3.5) + notes([36], 14, 3.8)
    return Song(
        title="A bright arrival",
        bpm=120,
        beats=18,
        seed=8203,
        master_gain=0.65,
        tracks=[
            Track(name="Identity", instrument="marimba", gain=0.45, pan=0.15, notes=lead),
            Track(name="Harmony", instrument="electric_piano", gain=0.32, pan=-0.2, notes=harmony),
            Track(name="Bass", instrument="bass", gain=0.3, notes=bass),
        ],
    )


def revise(song, brief):
    data = song.model_dump(mode="json")
    if brief == "video":
        for track in data["tracks"]:
            if track["name"] in {"Kick", "Hat"}:
                track["gain"] *= 0.45
    elif brief == "game":
        # Removing the chromatic tension layer preserves motif, groove and period.
        data["tracks"] = [track for track in data["tracks"] if track["name"] != "Tension"]
    elif brief == "presentation":
        data["tracks"].append(
            Track(
                name="Triumph",
                instrument="trumpet",
                gain=0.21,
                pan=-0.1,
                notes=notes([67, 72, 76], 0, 2.8, 0.5)
                + notes([67, 71, 74], 10, 3.4, 0.6)
                + notes([72, 76, 79], 14, 3.8, 0.68),
            ).model_dump(mode="json")
        )
    else:
        raise ValueError(brief)
    return Song.model_validate(data)


def revision_contract(original, revised, brief):
    before, after = original.model_dump(mode="json"), revised.model_dump(mode="json")
    checks = {
        "duration_preserved": original.seconds == revised.seconds,
        "seed_preserved": original.seed == revised.seed,
        "tempo_preserved": before["bpm"] == after["bpm"]
        and before["tempo_map"] == after["tempo_map"],
    }
    checks["global_settings_preserved"] = {
        key: value for key, value in before.items() if key != "tracks"
    } == {key: value for key, value in after.items() if key != "tracks"}
    tracks = {track["name"]: track for track in after["tracks"]}
    expected_names = {track["name"] for track in before["tracks"]}
    if brief == "game":
        expected_names.remove("Tension")
    elif brief == "presentation":
        expected_names.add("Triumph")
    checks["expected_track_set"] = set(tracks) == expected_names
    for track in before["tracks"]:
        name = track["name"]
        if brief == "game" and name == "Tension":
            checks["tension_removed"] = name not in tracks
        elif brief == "video" and name in {"Kick", "Hat"}:
            expected = dict(track, gain=track["gain"] * 0.45)
            checks[name + "_gain_only"] = tracks[name] == expected
        else:
            checks[name + "_unchanged"] = tracks[name] == track
    if brief == "presentation":
        checks["trumpet_added"] = "Triumph" in tracks
    if not all(checks.values()):
        raise AssertionError(checks)
    return checks


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_pcm(path):
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 2 or wav.getsampwidth() != 2:
            raise ValueError("Expected stereo 16-bit WAV")
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").reshape(
            -1, 2
        ), wav.getframerate()


def verify_loop(path, twice_path):
    """Measure the actual PCM join, and export two unmodified cycles for audition."""
    pcm, rate = read_pcm(path)
    if len(pcm) < 2:
        raise ValueError("A loop needs at least two frames")
    if Path(path).resolve() == Path(twice_path).resolve():
        raise ValueError("Keep the loop and two-cycle preview paths distinct")
    join = pcm[0].astype(np.int32) - pcm[-1].astype(np.int32)
    slope = np.diff(np.concatenate((pcm[-2:], pcm[:2])).astype(np.int32), axis=0)
    with wave.open(str(twice_path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(np.tile(pcm, (2, 1)).astype("<i2").tobytes())
    two, _ = read_pcm(twice_path)
    result = {
        "join_jump_pcm": int(np.max(np.abs(join))),
        "join_local_step_pcm": int(np.max(np.abs(slope))),
        "first_frame_pcm": pcm[0].tolist(),
        "last_frame_pcm": pcm[-1].tolist(),
        "two_cycles_frames": len(two),
        "two_cycles_seconds": len(two) / rate,
        "cycles_identical": bool(np.array_equal(two[: len(pcm)], two[len(pcm) :])),
        "method": (
            "Dry duration-gated arrangement; articulated rests at bar lines; no crop or crossfade."
        ),
        "auditioned": False,
    }
    if (
        result["join_jump_pcm"] != 0
        or result["join_local_step_pcm"] > 1
        or not result["cycles_identical"]
    ):
        raise AssertionError(result)
    return result


def deliver(song, folder, brief):
    folder.mkdir(parents=True, exist_ok=True)
    song.save(folder / "score.json")
    shutil.copyfile(__file__, folder / "composer.py")
    inspection = inspect_score(song)
    save_json(folder / "inspection.json", inspection)
    for target in ("render", "midi"):
        if not inspection["readiness"][target]["ready"]:
            raise ValueError(inspection["issues"])
    report = render(song, folder / "song.wav")
    save_json(folder / "report.json", report)
    save_json(folder / "midi-report.json", export_midi(song, folder / "song.mid"))
    save_json(folder / "analysis.json", analyze_wav(folder / "song.wav"))
    # Independently check float synthesis, byte-identical export, and the saved PCM.
    floating = render_audio(song).audio
    render(song, folder / "reproduction.wav")
    pcm, rate = read_pcm(folder / "song.wav")
    sha = hashlib.sha256((folder / "song.wav").read_bytes()).hexdigest()
    repeated_sha = hashlib.sha256((folder / "reproduction.wav").read_bytes()).hexdigest()
    checks = {
        "seconds": len(pcm) / rate,
        "frames": len(pcm),
        "sample_rate": rate,
        "expected_frames": round(song.seconds * rate),
        "channels": pcm.shape[1],
        "float_finite": bool(np.isfinite(floating).all()),
        "float_peak": float(np.max(np.abs(floating))),
        "full_scale_samples": int(np.count_nonzero((pcm == -32768) | (pcm == 32767))),
        "last_10ms_peak_pcm": int(np.max(np.abs(pcm[-rate // 100 :].astype(np.int32)))),
        "byte_reproducible": sha == repeated_sha,
        "wav_sha256": sha,
        "midi_seconds": mido.MidiFile(folder / "song.mid").length,
        "auditioned": False,
    }
    if not (
        checks["frames"] == checks["expected_frames"]
        and checks["channels"] == 2
        and checks["float_finite"]
        and checks["float_peak"] < 1
        and checks["full_scale_samples"] == 0
        and checks["byte_reproducible"]
        and checks["last_10ms_peak_pcm"] == 0
        and abs(checks["midi_seconds"] - song.seconds) < 0.001
    ):
        raise AssertionError(checks)
    if brief == "video":
        cue = next(track for track in song.tracks if track.name == "Reveal")
        checks["cue_seconds"] = song.beat_to_seconds(cue.notes[0].start)
        if checks["cue_seconds"] != 20:
            raise AssertionError(checks)
    if brief == "game":
        checks["loop"] = verify_loop(folder / "song.wav", folder / "two-cycles.wav")
    save_json(folder / "acceptance.json", checks)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path("output/creative-workflows"))
    parser.add_argument("--scores-only", action="store_true")
    parser.add_argument("--brief", choices=["all", *BRIEFS], default="all")
    parser.add_argument("--version", choices=["all", "v1", "v2"], default="all")
    args = parser.parse_args()
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        parser.error("Use a fresh or empty output folder to preserve previous candidates.")
    args.output.mkdir(parents=True, exist_ok=True)
    result = {
        "python": sys.version,
        "platform": platform.platform(),
        "auditioned": False,
        "scores_only": args.scores_only,
        "briefs": {},
    }
    lockfile = Path.cwd() / "uv.lock"
    if lockfile.is_file():
        shutil.copyfile(lockfile, args.output / "uv.lock")
    for brief, builder in (("video", video), ("game", game), ("presentation", presentation)):
        if args.brief not in {"all", brief}:
            continue
        original = builder()
        revised = revise(original, brief)
        item = {
            **BRIEFS[brief],
            "revision_constraints": revision_contract(original, revised, brief),
        }
        for version, song in (("v1", original), ("v2", revised)):
            if args.version not in {"all", version}:
                continue
            folder = args.output / brief / version
            folder.mkdir(parents=True, exist_ok=True)
            save_json(
                folder / "brief.json",
                {**BRIEFS[brief], "version": version, "section_time_unit": "seconds"},
            )
            if args.scores_only:
                shutil.copyfile(__file__, folder / "composer.py")
                song.save(folder / "score.json")
                save_json(folder / "inspection.json", inspect_score(song))
                save_json(folder / "midi-report.json", export_midi(song, folder / "song.mid"))
            else:
                item[version] = deliver(song, folder, brief)
            item.setdefault("artifacts", {})[version] = {
                path.name: path.relative_to(args.output).as_posix()
                for path in sorted(folder.iterdir())
                if path.is_file()
            }
            print(f"{brief}/{version}: {song.seconds:g}s", flush=True)
        result["briefs"][brief] = item
    save_json(args.output / "manifest.json", result)


if __name__ == "__main__":
    main()
