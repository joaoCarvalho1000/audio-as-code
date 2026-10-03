# Using Audio as Code from an agent

Start with the [portable composition skill](../skills/audio-as-code/SKILL.md).
It covers setup, interpreting a musical brief, composing, rendering, checking,
delivering files, and revisions. Give your agent this checkout (or the website's
source ZIP) and say:

```text
Read skills/audio-as-code/SKILL.md in the Audio as Code source folder and use it
to create an original 30-second hopeful instrumental for piano, marimba and bass.
Build a memorable motif, vary the second phrase, and finish with a clear cadence.
Set up locally, validate and render, then deliver WAV, MIDI, editable score,
composer source and report. Say whether you listened.
```

For the next version: “Keep the motif and duration, make the middle quieter, and
let the final chord ring longer.” Keep both versions so the user can compare.
The human does not need to write Python; the agent needs a local shell, Python
3.10+, and permission to write within the chosen project. Initial dependencies
need a network connection or a populated cache. The runtime needs no provider API
key or bundled AI model. Reading the skill as instructions does not depend on a
vendor's skill installation mechanism.

For complete original video, game and presentation deliveries, run
`uv run --no-dev python examples/creative_workflows.py output/creative-workflows`
from the source folder. It builds first versions and constrained revisions with
WAV/MIDI/JSON, copied composer, inspection, reports and acceptance checks. Use a
fresh destination; add `--scores-only` for a fast composition pass or
`--brief game --version v2` to select one candidate. See the
[creative workflow guide](creative-workflows.md) for exact cuts, cues, loop joins
and revision preservation. Full rendering includes extra synthesis passes to
check finite samples and byte reproducibility; allow several minutes.

The CLI is the initial agent integration. Call it through your existing shell tool; no framework-specific AI SDK is required. An MCP server is not implemented yet.

## Commands

| Operation | Command | JSON response |
| --- | --- | --- |
| Identify engine | `aac --version` | Engine version |
| Discover playable voices | `aac instruments` | Families, engines, available voices, controls, MIDI mappings |
| Inspect a family | `aac instruments --all --family woodwinds` | Catalog entries with explicit availability status |
| Discover score shape | `aac schema` | JSON Schema |
| Start from an example | `aac demo -o song.json` | Score path and title |
| Check score | `aac validate song.json` | Validity, tempo, length, track/note counts |
| Inspect before rendering | `aac inspect song.json` | Per-track timing, pitches, polyphony, export readiness and structured issues |
| Render | `aac render song.json -o song.wav --report report.json` | Render metadata, measurements, warnings |
| Render stems | `aac render song.json -o song.wav --stems stems` | Same report plus track-to-file mapping |
| Export | `aac midi song.json -o song.mid` | MIDI path, duration, export warnings |
| Check audio | `aac analyze song.wav` | Signal measurements |

MIDI warnings describe features present in the score, such as tone controls,
percussion or effects. The receiver determines instrument sound in every MIDI export.

When running from the source checkout, first run `uv sync --locked`, then prefix
commands with `uv run`. `uv run python -m audio_as_code` is an equivalent entry
point. The package is not published to PyPI; use the local checkout. Commands
need no network after installation. Run from the checkout root, or invoke the
installed environment's Python by its absolute path.

Output files are replaced if they already exist. Input score, output audio,
report, and stem filenames must be distinct, including symlink and existing
hard-link aliases. The CLI and Python renderer check for file/directory conflicts before
rendering. This is not a transactional write guarantee: permission failures,
disk exhaustion, or paths changed by another process can still leave partial
output. Use a fresh output directory for each candidate when comparing
revisions; unrelated or stale files in that directory are not removed.

Scores must be UTF-8 JSON; an optional UTF-8 BOM is accepted. Use `aac schema -o
schema.json` to save a schema directly. In Windows PowerShell 5.1, shell `>`
redirection can produce UTF-16 text, which is not a supported score encoding.
Prefer `Song.save()`, `aac demo -o`, or an explicitly UTF-8 file writer.

Successful commands exit 0 and emit JSON on stdout. Failed commands exit 2 and emit one JSON object on stderr. Score errors have this shape:

```json
{
  "error": "invalid_score",
  "issues": [{
    "path": ["tracks", 0, "notes", 0, "duration"],
    "message": "Input should be greater than 0",
    "type": "greater_than"
  }],
  "hint": "Correct the issue paths, then run aac validate again. Use aac schema for the score contract."
}
```

Cross-field errors, such as a note extending beyond the song, may have an empty
path and identify the track and note in the message. I/O, argument, MIDI, and
renderer errors use `{"error":"operation_failed","message":"...","hint":"..."}`.
Treat error codes and issue paths as structured data; message and hint wording
may change. Accept additive response fields. Validation does not guarantee that
a score fits every backend: WAV limits duration, while MIDI limits channels and
overlapping pitches. Help (`--help`) is plain text on stdout with exit 0;
`--version` is JSON. Parse stderr only when a command fails.

## Call the CLI safely

An agent running inside the installed Python environment can avoid shell quoting
and locate the correct interpreter with `sys.executable`:

```python
import json
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "audio_as_code", "validate", "output/song.json"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    timeout=60,
    check=False,
)
if result.returncode == 0:
    score_summary = json.loads(result.stdout)
elif result.returncode == 2:
    diagnostic = json.loads(result.stderr)
    print(diagnostic)
else:
    raise RuntimeError(result.stderr or "Process failed without a CLI diagnostic")
```

Pass arguments as an array and avoid `shell=True`. Resolve relative score and
output paths against your chosen working directory. A missing executable,
process timeout, or termination is a process-level failure; it does not promise
a JSON diagnostic. Set a larger timeout for renders based on score length and
voice complexity. Start with short previews to bound memory and iteration time.

Keep discovery separate from rendering: `aac instruments` returns playable
voices, `aac instruments --all` can also describe planned voices, and
`aac schema` returns the exact accepted score structure. Never infer playability
from a musical instrument name or substitute a generic voice silently.

## Suggested workflow

Discover available instruments before composing. `aac instruments` only lists playable voices; `--all` includes planned instruments, which cannot be placed in a score. Filters include `--family` and `--engine`. Read [the instrument foundation](instrument-foundation.md) for the full family/engine structure. The framework's instrument policy is code-generated synthesis.

Start with four or eight bars. Use explicit rests, one stable rhythmic foundation, a bass line, and one harmonic or melodic part. Keep each part on a named track. Save the JSON score so another agent or a human can inspect and edit it.

Validate before rendering. Render a short arrangement, check the report, and audition the WAV when your environment supports audio. Edit the score and repeat. A low RMS or high peak is not inherently a musical error; these are diagnostics, not a reward function.

Report fields:

- `before_gain`: float mix measurements before optional peak attenuation.
- `gain_applied`: global attenuation, at most 1.
- `audio`: float mix measurements after attenuation, before PCM quantization.
- `wav`: measurements from the saved 16-bit file.
- `warnings`: silence, gain reduction, clipping, or sub-sample notes.
- `score_sha256`, `engine_version`, `numpy_version`, and `seed`: reproduction metadata.

`clipped_samples` in float measurements counts individual channel samples with absolute amplitude at least 1. `full_scale_samples` in WAV analysis counts samples at a PCM rail; this is evidence of full-scale values, not proof of upstream clipping. Silence means exact digital zero. dB values are `null` for silence so output remains valid JSON.

## Inspecting a score before rendering

Before rendering, use `aac inspect score.json` or `inspect_score(song)` to inspect
the arrangement without synthesizing audio or writing files. A successful
inspection exits 0 even if an export is blocked. Check
`readiness.render.ready` and `readiness.midi.ready`, then fix relevant `issues`
with `severity: "error"`. Issue codes and paths provide structured feedback;
warnings explain lossy exports and other limitations. See the
[inspection contract](score-inspection.md) for details.

## Editing scores in Python

```python
from audio_as_code import Song

data = Song.load("song.json").model_dump(mode="json")
data["tracks"][0]["gain"] = 0.4
revised = Song.model_validate(data)
revised.save("revised.json")
```

Use normal model construction or `model_validate()` to check revisions. Pydantic's `model_copy(update=...)` and `model_construct()` bypass validation; the export boundaries revalidate, but relying on unchecked objects is discouraged.

## Current constraints

All 49 catalog entries have generated prototypes. Read each entry's `description`, `tone_controls`, `default_tone`, and `default_decay_seconds` before composing. For example, a decaying string accepts `"tone": {"brightness": 0.6, "decay_seconds": 3}`; violin accepts `"tone": {"vibrato_depth_cents": 14, "vibrato_rate_hz": 5.5}`. Unsupported controls are rejected. Longer tone decay alone does not extend a note. Optional note/track `release_seconds` adds an audible release after note-off; zero preserves the original gate behavior. See the [orchestra guide](orchestra.md) for model boundaries, control ranges, and the `drum_machine` pitch map.

The schema accepts no arbitrary extra fields and rejects unsupported versions, non-finite numbers, duplicate track names, out-of-range pitches, and notes extending beyond the arrangement. Names must be unique within a score. All score timing is in quarter-note beats. Optional `tempo_map` entries change BPM at ordered beat positions. Track gain/pan and song master-gain automation use ordered points with linear or step interpolation. Track/song effects support generated delay and reverb. There is no meter metadata, swing field, clip graph or sample loading. Swing can be expressed by placing individual notes at explicit beat positions.

For `piano` only, `Track.pedal` accepts ordered `PedalEvent(beat=..., down=True/False)`
events and MIDI exports binary CC64. This models a binary damper gate, with no
half-pedaling or sympathetic resonance. Other voices, including `electric_piano`,
reject nonempty pedal lists. The automatic final lift can add a damper tail beyond
the score length: verify actual WAV duration for fixed media cuts. See the
[piano sustain guide](piano-sustain.md) for event ordering and release precedence.

The renderer uses the entire arrangement length plus automatic release/effect tails and limits the total to 300 seconds. `Song.seconds` is the score duration; `Song.render_seconds` includes tails. MIDI carries tempo changes but omits automation, effects, releases and audio tails, with a warning. Stems omit master effects; their sum differs from a master-processed mix. The score itself may describe longer music for MIDI export. Very short notes can disappear on the sample grid; very high notes can be silent at a low sample rate when their fundamental exceeds Nyquist. MIDI export rejects notes that quantize to zero duration or overlap another occurrence of the same pitch on the same channel.

Keep the input score, dependency lock, runtime/platform information, and report beside any audio you intend to reproduce. Use listening to assess phrasing, harmony, timbre, and overall musical quality.
