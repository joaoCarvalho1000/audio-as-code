"""Every successful command emits JSON. Failures emit JSON to stderr and exit 2."""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from ._paths import check_paths as _check_paths
from .demo import demo_song
from .inspection import inspect_score
from .instruments import ENGINES, FAMILIES, instrument_catalog
from .midi import export_midi
from .model import Song
from .render import analyze_wav, render


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ArgumentError(f"{self.prog}: {message}")


class ArgumentError(ValueError):
    """An invalid CLI invocation, with the existing operation_failed contract."""


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
    wav = commands.add_parser("render", help="Render a score to stereo PCM WAV")
    wav.add_argument("score", help="Path to a UTF-8 JSON score (render limit: 300 seconds)")
    wav.add_argument("-o", "--output", required=True, help="Destination 16-bit stereo WAV")
    wav.add_argument("--stems", metavar="DIRECTORY", help="Write numbered per-track WAV files")
    wav.add_argument(
        "--no-normalize", action="store_true", help="Disable peak attenuation; loud mixes may clip"
    )
    wav.add_argument("--report", help="Also save the JSON render report to this path")
    midi = commands.add_parser("midi", help="Export a score as a type-1 MIDI file")
    midi.add_argument("score", help="Path to a UTF-8 JSON score")
    midi.add_argument("-o", "--output", required=True, help="Destination type-1 MIDI file")
    analyze = commands.add_parser("analyze", help="Measure a 16-bit PCM WAV file")
    analyze.add_argument("audio", help="Path to an existing 16-bit PCM WAV file")
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
        return "Use an intact 16-bit PCM WAV file, such as one produced by aac render."
    return "Check the message and command options; for score inputs, run aac validate first."


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "instruments":
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
            elif args.command == "midi":
                _check_paths([args.score, args.output])
                result = export_midi(song, args.output)
            else:
                paths = [args.score, args.output]
                if args.report:
                    paths.append(args.report)
                if args.stems:
                    paths.extend(
                        Path(args.stems) / f"{i + 1:02d}.wav" for i in range(len(song.tracks))
                    )
                _check_paths(paths, [args.stems] if args.stems else [])
                result = render(
                    song, args.output, normalize=not args.no_normalize, stems_dir=args.stems
                )
                if args.report:
                    _write_json(args.report, result)
        print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
        return 0
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
