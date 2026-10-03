"""Exercise an installed artifact from a temporary working directory, never the checkout."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from importlib.metadata import distribution
from pathlib import Path

import audio_as_code
from audio_as_code import (
    Note,
    Pattern,
    Song,
    Track,
    analyze_wav,
    export_midi,
    get_instrument,
    inspect_score,
    render,
)


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    package = Path(audio_as_code.__file__).resolve()
    if package.is_relative_to(repo / "src"):
        raise SystemExit("Smoke test imported the checkout; install the built wheel in isolation")
    metadata = distribution("audio-as-code")
    assert metadata.version == audio_as_code.__version__
    assert (package.parent / "py.typed").is_file()
    console = Path(sys.executable).with_name("aac.exe" if sys.platform == "win32" else "aac")
    with tempfile.TemporaryDirectory(prefix="aac-installed-") as folder:
        work = Path(folder)
        for command in ([str(console)], [sys.executable, "-m", "audio_as_code"]):
            version = subprocess.run(
                [*command, "--version"], cwd=work, capture_output=True, text=True, check=True
            )
            assert json.loads(version.stdout) == {"version": metadata.version}
            subprocess.run([*command, "--help"], cwd=work, capture_output=True, check=True)
        phrase = Pattern.sequence(["C4"], step=0.25)
        phrase = phrase.overlay(phrase.transpose(12), offset=0.25).stretch(2).scale_velocity(0.5)
        song = Song(
            title="Installed artifact smoke test",
            bpm=120,
            beats=1,
            sample_rate=22050,
            seed=7,
            tracks=[Track(name="Lead", instrument="sine", notes=phrase.notes)],
        )
        score = work / "score.json"
        song.save(score)
        assert Song.load(score) == song
        inspection = inspect_score(song)
        assert inspection["summary"]["note_count"] == 2
        assert inspection["readiness"]["render"]["ready"]
        assert inspection["readiness"]["midi"]["ready"]
        inspected = subprocess.run(
            [str(console), "inspect", str(score)],
            cwd=work,
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(inspected.stdout) == inspection
        report = render(song, work / "score.wav")
        export_midi(song, work / "score.mid")
        assert report["wav"] == analyze_wav(work / "score.wav")
        assert not report["wav"]["silent"] and not report["wav"]["full_scale_samples"]
        validation = subprocess.run(
            [str(console), "validate", str(score)],
            cwd=work,
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(validation.stdout)["valid"]
        for voice in ("mandolin", "kalimba", "celesta", "recorder"):
            info = get_instrument(voice)
            probe = Song(
                bpm=120,
                beats=1,
                sample_rate=22050,
                tracks=[
                    Track(
                        name=voice,
                        instrument=voice,
                        notes=[Note(pitch=info.preview_pitch, duration=1)],
                    )
                ],
            )
            voice_report = render(probe, work / f"{voice}.wav")
            assert not voice_report["wav"]["silent"]
            assert not voice_report["wav"]["full_scale_samples"]
            export_midi(probe, work / f"{voice}.mid")
        invalid = work / "invalid.json"
        invalid.write_text('{"tracks":[]}', encoding="utf-8")
        failure = subprocess.run(
            [str(console), "validate", str(invalid)],
            cwd=work,
            capture_output=True,
            text=True,
        )
        assert failure.returncode == 2 and not failure.stdout
        assert json.loads(failure.stderr)["error"] == "invalid_score"
    print(json.dumps({"version": metadata.version, "installed_artifact_smoke": "passed"}))


if __name__ == "__main__":
    main()
