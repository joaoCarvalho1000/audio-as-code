"""Every successful command emits JSON. Failures emit JSON to stderr and exit 2."""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from . import __version__
from ._cli_progress import progress_file
from ._paths import check_paths as _check_paths
from .demo import demo_song
from .inspection import inspect_score
from .instruments import ENGINES, FAMILIES, instrument_catalog
from .midi import export_midi
from .mixing import MixEdit, apply_mix, audition_song, inspect_mix
from .model import Song
from .project_setup import doctor, init_project
from .render import analyze_wav, render, render_preview


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ArgumentError(f"{self.prog}: {message}")


class ArgumentError(ValueError):
    """An invalid CLI invocation, with the existing operation_failed contract."""


class MixInputError(ValueError):
    """Invalid edit data, with locations in the edit file rather than the score."""

    def __init__(self, error: ValidationError) -> None:
        super().__init__("Invalid mix edits")
        self.issues = [
            {
                "path": ["edits", *item["loc"]],
                "message": item["msg"],
                "type": item["type"],
            }
            for item in error.errors(include_url=False)
        ]


def _render_arguments(parser: argparse.ArgumentParser, *, stems: bool) -> None:
    parser.add_argument("score", help="Path to a UTF-8 JSON score (render limit: 300 seconds)")
    parser.add_argument("-o", "--output", required=True, help="Destination stereo WAV")
    parser.add_argument(
        "--format",
        dest="wav_format",
        choices=("pcm16", "pcm24", "float32"),
        default="pcm16",
        help="WAV encoding (default: pcm16)",
    )
    if stems:
        parser.add_argument(
            "--stems", metavar="DIRECTORY", help="Write numbered per-track WAV files"
        )
    else:
        parser.set_defaults(stems=None)
    gain = parser.add_mutually_exclusive_group()
    gain.add_argument(
        "--no-normalize", action="store_true", help="Disable peak attenuation; PCM mixes may clip"
    )
    gain.add_argument(
        "--target-lufs",
        type=float,
        help="Target integrated loudness; requires the optional loudness extra",
    )
    parser.add_argument(
        "--peak-ceiling-dbfs",
        type=float,
        help="Sample-peak ceiling with --target-lufs (default: -1 dBFS; not true peak)",
    )
    parser.add_argument("--report", help="Also save the JSON render report to this path")
    parser.add_argument(
        "--progress-file",
        metavar="PATH",
        help="Write live JSON Lines progress here; stdout remains one JSON result",
    )


def _parser() -> argparse.ArgumentParser:
    parser = Parser(
        prog="aac",
        description="Audio as Code: compose, render, and inspect music locally.",
        epilog="Success: JSON on stdout, exit 0. Errors: JSON on stderr, exit 2. "
        "Run 'aac COMMAND --help' for command options.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=json.dumps({"version": __version__}),
        help="Print the installed engine version as JSON and exit",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a composition project in a new or empty folder")
    init.add_argument(
        "directory", help="New or empty project directory; existing files are preserved"
    )
    commands.add_parser("doctor", help="Check the imported runtime and local composition setup")
    instruments = commands.add_parser("instruments", help="Discover voices, families, and engines")
    instruments.add_argument("--all", action="store_true", help="Include planned instruments")
    instruments.add_argument("--family", choices=[family.id for family in FAMILIES])
    instruments.add_argument("--engine", choices=[engine.id for engine in ENGINES])
    demo = commands.add_parser("demo", help="Write an example JSON score")
    demo.add_argument("-o", "--output", default="demo.json", help="Score path (default: demo.json)")
    schema = commands.add_parser("schema", help="Print the versioned JSON Schema")
    schema.add_argument("-o", "--output", help="Write schema to a file instead of stdout")
    validate = commands.add_parser("validate", help="Validate a JSON score")
    validate.add_argument("score", help="Path to a UTF-8 JSON score")
    inspect = commands.add_parser("inspect", help="Inspect score facts and static export readiness")
    inspect.add_argument("score", help="Path to a UTF-8 JSON score; does not render or write files")
    mix = commands.add_parser("mix", help="Inspect or revise score mix settings without rendering")
    mix.add_argument("score", help="Path to a UTF-8 JSON score")
    mix.add_argument("--edits", help="UTF-8 JSON array of ordered MixEdit objects")
    mix.add_argument("-o", "--output", help="Revised score path; required for edits or audition")
    mix.add_argument(
        "--solo", action="append", default=[], help="Exact track name; repeat for a group"
    )
    mix.add_argument(
        "--mute", action="append", default=[], help="Exact track name; mute wins over solo"
    )
    mix.add_argument("--report", help="Also save the JSON settings/change report")
    wav = commands.add_parser("render", help="Render a score to stereo WAV")
    _render_arguments(wav, stems=True)
    preview = commands.add_parser(
        "preview", help="Export an excerpt with full render context (costs a full render)"
    )
    _render_arguments(preview, stems=False)
    preview.add_argument("--start", type=float, required=True, help="Excerpt start in seconds")
    preview.add_argument(
        "--duration", type=float, required=True, help="Excerpt duration in seconds"
    )
    midi = commands.add_parser("midi", help="Export a score as a type-1 MIDI file")
    midi.add_argument("score", help="Path to a UTF-8 JSON score")
    midi.add_argument("-o", "--output", required=True, help="Destination type-1 MIDI file")
    analyze = commands.add_parser("analyze", help="Measure a PCM or float WAV file")
    analyze.add_argument("audio", help="Path to a 16/24-bit PCM or 32-bit float WAV file")
    return parser


def _write_json(path: str, data: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _error_hint(error: Exception) -> str:
    if isinstance(error, ArgumentError):
        return "Run aac --help or aac COMMAND --help to check arguments."
    if isinstance(error, FileNotFoundError):
        return "Check the input path and current working directory; quote paths containing spaces."
    if isinstance(error, PermissionError):
        return "Choose a writable output directory and close applications holding the file open."
    if isinstance(error, (wave.Error, EOFError)):
        return (
            "Use an intact 16-bit PCM WAV, 24-bit PCM WAV, or 32-bit float WAV, "
            "such as one produced by aac render."
        )
    return "Check the message and command options; for score inputs, run aac validate first."


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command in {"render", "preview"}:
            if args.peak_ceiling_dbfs is not None and args.target_lufs is None:
                raise ArgumentError("--peak-ceiling-dbfs requires --target-lufs")
        if args.command == "init":
            result = init_project(args.directory)
        elif args.command == "doctor":
            result = doctor()
            if not result["ok"]:
                print(
                    json.dumps(
                        {
                            **result,
                            "error": "operation_failed",
                            "message": "Environment checks failed",
                            "hint": "Follow the failed checks' hints, then run aac doctor again.",
                        },
                        ensure_ascii=True,
                        allow_nan=False,
                    ),
                    file=sys.stderr,
                )
                return 2
        elif args.command == "instruments":
            result = instrument_catalog(
                family=args.family, engine=args.engine, include_planned=args.all
            )
        elif args.command == "demo":
            _check_paths([args.output])
            song = demo_song()
            song.save(args.output)
            result = {"output": args.output, "title": song.title}
        elif args.command == "schema":
            result = Song.model_json_schema()
            if args.output:
                _check_paths([args.output])
                _write_json(args.output, result)
                result = {"output": args.output, "schema_version": "1"}
        elif args.command == "analyze":
            result = analyze_wav(args.audio)
        else:
            song = Song.load(args.score)
            if args.command == "validate":
                result = {
                    "valid": True,
                    "schema_version": song.schema_version,
                    "title": song.title,
                    "bpm": song.bpm,
                    "beats": song.beats,
                    "duration_seconds": song.seconds,
                    "render_duration_seconds": song.render_seconds,
                    "tracks": len(song.tracks),
                    "notes": sum(len(t.notes) for t in song.tracks),
                }
            elif args.command == "inspect":
                result = inspect_score(song)
            elif args.command == "mix":
                if (args.edits or args.solo or args.mute) and not args.output:
                    raise ArgumentError("mix edits and auditions require --output")
                paths = [args.score]
                paths.extend(p for p in (args.edits, args.output, args.report) if p)
                _check_paths(paths)
                if args.output:
                    edits = []
                    if args.edits:
                        payload = json.loads(Path(args.edits).read_text(encoding="utf-8"))
                        try:
                            edits = TypeAdapter(list[MixEdit]).validate_python(payload)
                        except ValidationError as error:
                            raise MixInputError(error) from error
                    revision = apply_mix(song, edits)
                    revised = audition_song(revision.song, solo=args.solo, mute=args.mute)
                    result = {
                        **revision.report,
                        "output": args.output,
                        "after": inspect_mix(revised),
                    }
                    if args.solo or args.mute:
                        result["audition"] = {
                            "solo": args.solo,
                            "mute": args.mute,
                            "precedence": "mute wins; empty solo includes all tracks",
                            "before": inspect_mix(revision.song),
                            "after": inspect_mix(revised),
                        }
                    revised.save(args.output)
                else:
                    result = inspect_mix(song)
                if args.report:
                    _write_json(args.report, result)
            elif args.command == "midi":
                _check_paths([args.score, args.output])
                result = export_midi(song, args.output)
            else:
                paths = [args.score, args.output]
                if args.report:
                    paths.append(args.report)
                if args.progress_file:
                    paths.append(args.progress_file)
                if args.stems:
                    paths.extend(
                        Path(args.stems) / f"{i + 1:02d}.wav" for i in range(len(song.tracks))
                    )
                _check_paths(paths, [args.stems] if args.stems else [])
                with progress_file(args.progress_file) as progress:
                    options = {
                        "normalize": not args.no_normalize,
                        "wav_format": args.wav_format,
                        "progress": progress,
                        "target_lufs": args.target_lufs,
                        "peak_ceiling_dbfs": (
                            args.peak_ceiling_dbfs if args.peak_ceiling_dbfs is not None else -1.0
                        ),
                    }
                    if args.command == "preview":
                        result = render_preview(
                            song,
                            args.output,
                            start_seconds=args.start,
                            duration_seconds=args.duration,
                            **options,
                        )
                    else:
                        result = render(song, args.output, stems_dir=args.stems, **options)
                if args.report:
                    _write_json(args.report, result)
        print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
        return 0
    except KeyboardInterrupt:
        print(
            json.dumps(
                {
                    "error": "operation_failed",
                    "message": "Operation interrupted",
                    "hint": "Retry the command when ready.",
                }
            ),
            file=sys.stderr,
        )
        return 2
    except MixInputError as error:
        print(
            json.dumps(
                {
                    "error": "invalid_mix_edits",
                    "issues": error.issues,
                    "hint": "Correct the indicated entries in the --edits JSON array; "
                    "gain is absolute, trim_db is relative, and track names must match exactly.",
                }
            ),
            file=sys.stderr,
        )
        return 2
    except ValidationError as error:
        issues = [
            {"path": list(item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in error.errors(include_url=False)
        ]
        print(
            json.dumps(
                {
                    "error": "invalid_score",
                    "issues": issues,
                    "hint": "Correct the issue paths, then run aac validate again. "
                    "Use aac schema for the score contract.",
                }
            ),
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError, wave.Error, EOFError) as error:
        print(
            json.dumps(
                {"error": "operation_failed", "message": str(error), "hint": _error_hint(error)}
            ),
            file=sys.stderr,
        )
        return 2
