---
name: audio-as-code
description: Compose or revise original instrumental music with the local Audio as Code framework, delivering rendered WAV, MIDI, editable scores, and reproducible source. Use when a user wants music made with this framework or changes to an existing Audio as Code composition.
---

# Audio as Code

Turn the user's musical brief into actual local artifacts. You make the artistic
decisions; the framework validates, synthesizes, exports, and measures. A person
can describe the music without writing code. You need a shell, a writable project,
and Python 3.10+. No provider API key or language model is bundled or required by
the renderer. This is a portable instruction file, not a hosted API or MCP server.

## Get the local tool ready

Look for an existing Audio as Code checkout (`pyproject.toml` and
`src/audio_as_code/`) or an installed `aac --version` / `python -m audio_as_code
--version`. Reuse the project's environment.

To add the library to an existing Python project managed by uv, run from that
project's root:

```sh
uv add "audio-as-code @ git+https://github.com/joaoCarvalho1000/audio-as-code.git"
uv run --locked aac --version
uv run --locked aac instruments
uv run --locked aac schema
```

This installs from the public source repository; there is no PyPI release.
Git must be installed. Keep the project's `pyproject.toml` and `uv.lock`: the lock
records the resolved Git commit and dependency versions. An explicit source pin
uses `git+https://github.com/joaoCarvalho1000/audio-as-code.git@FULL_COMMIT_SHA`
in the same dependency string, replacing `FULL_COMMIT_SHA` with a verified commit.
Use `uv run --locked` for composition and rendering in this project. Do not use
the framework's `uv.lock` to replace an existing application's lockfile. Read this
skill from the same source revision when you need version-specific instructions;
the installed catalog, schema and CLI help describe that revision's capabilities.

For a standalone project, download/extract the source instead. From its root:

```sh
uv sync --locked --no-dev
uv run --no-dev aac --version
uv run --no-dev aac instruments
uv run --no-dev aac schema
```

For the standalone route, use the source ZIP URL supplied with the user's website
prompt, or the website's **Download source** link. Download and extract into the
working project, then run the commands above from the extracted folder containing
`pyproject.toml`. Read the bundled `skills/audio-as-code/SKILL.md` for that version.
Use only the public repository above or a source location supplied by the user;
do not invent a registry release or another installation URL. If neither source
route is accessible, ask for the source ZIP or local checkout path.

Without uv, create a local environment with `python -m venv .venv`, then run
`.venv/Scripts/python.exe -m pip install -e .` on Windows or
`.venv/bin/python -m pip install -e .` on macOS/Linux. Use that interpreter with
`-m audio_as_code` in place of `uv run --no-dev aac`. No shell activation is necessary.
The `--no-dev` option installs only runtime dependencies. Initial dependency
installation needs network access or a populated cache;
rendering afterward is offline. Do not install into the user's global Python.

## Compose the brief

Infer a useful first version from the requested mood, duration, instruments, use,
and form. Ask only for missing decisions that materially affect the result; do
not require a questionnaire or approval of a plan. State significant assumptions
briefly. Honor an existing composition and the scope of a revision.

Discover current playable IDs and each voice's `tone_controls` with
`aac instruments`; `--all` also includes planned voices. Read `aac schema` for the
accepted fields. Never claim an unavailable instrument is implemented or silently
substitute another voice. Sounds must come from the framework's procedural,
physical, or modal synthesis: no recordings, SoundFonts, sample-library backends,
or measured impulse responses as instrument sources.

Write a UTF-8 JSON score directly or write a reproducible Python composer using
`Note`, `Pattern`, `Song`, and `Track`. Keep the composer when you use one. Save
scores with `Song.save()` or an explicit UTF-8 writer; PowerShell 5.1 `>` can write
unsupported UTF-16. Use a fresh folder such as `output/my-piece/v1/` per candidate.

Make an original motif, develop it through rhythm, harmony, register or texture,
and provide an intentional ending (or a loop seam when requested). Give parts
musical roles and use rests, accents and changing density. A short identity sting
needs less development than a full piece. `aac demo` is an installation check or
starting reference, not an original answer to an unrelated musical brief.

Score essentials:

- `schema_version` is `"1"`; time is quarter-note beats from zero. BPM is 20–300.
  With no `tempo_map`, seconds = `beats * 60 / bpm`; otherwise tempo changes are
  ordered `{beat, bpm}` steps. Plan a WAV of at most 300 seconds including tails.
- Notes have `pitch`, `start`, `duration`, `velocity`; `start + duration <= beats`.
  Pitch is MIDI 0–127 or a name such as `C4` (= 60). Velocity is greater than 0
  and at most 1. Omit a note for a rest. `release_seconds` (0–10) can extend the
  sound after note-off; a note inherits its track release unless overridden.
- Tracks have unique `name`, playable `instrument`, `notes`, and optional `gain`,
  `pan`, `tone`. Gain and master gain are 0–1; pan is -1 to 1. Tone is per track
  and accepts only that voice's supported controls. Omit it for basic voices.
- Use 1–64 tracks and at most 100,000 notes. The format forbids extra fields;
  express sections, meter and swing through explicit notes and timing. Piano-only
  `pedal` accepts ordered `{beat, down}` events (`down` is a boolean), alternating
  down/up starting with down. The `piano` voice supports this binary damper gate;
  other instruments, including `electric_piano`, reject nonempty pedal lists.
  An open pedal lifts at song end and can add a damper tail, so check rendered
  duration. Read `docs/piano-sustain.md` for release precedence and limitations.
  Optional automation lanes target track `gain`/`pan` or song
  `master_gain`, using ordered `{beat, value}` points with `linear` or `step`
  interpolation. Values are absolute, not multipliers. Song and track `effects`
  accept ordered procedural `delay`/`reverb` chains; inspect the schema before
  writing their parameters. Release and effect tails extend the rendered WAV.
- For MIDI, use at most 15 melodic tracks, one track per individual drum ID,
  no overlapping same-pitch notes on a channel, and durations of at least one
  tick (1/480 beat). A `drum_machine` track shares channel 10 with individual drums;
  consult its catalog pitch map and avoid collisions.
- Keep the seed fixed across revisions unless changing stochastic excitation is
  intended. Reproducibility requires the same score, runtime and platform.

For a fixed video cut or presentation sting, convert the requested seconds to
beats, place cues explicitly, and plan the ending inside that duration. Check
`Song.render_seconds` as well as `Song.seconds`: releases and effects can extend
the WAV. At constant tempo a 30-second piece at 96 BPM is 48 beats and a cue at
20 seconds is beat 32. Keep section/cue metadata in a sidecar; custom score fields
are rejected. Check the exported WAV's actual frames against the target seconds
times sample rate, allowing one sample only when the target cannot be represented
exactly. Do not assume trimming an active tail creates a settled ending.

For a loop, choose a musical period first. A dry arrangement with duration-gated
notes and intentional rests at the bar line is one supported approach. Measure
the saved PCM join and neighboring sample steps, export two unchanged cycles,
and audition their middle join when possible. Endpoint agreement alone does not
prove a convincing musical loop. Effect tails, releases and continuous sustained
textures need deliberate boundary handling; there is no general loop-export API.
The source example `examples/creative_workflows.py` implements three original
briefs and constrained revisions; `docs/creative-workflows.md` explains the checks.

## Render, inspect, revise

Use your chosen environment prefix. These commands assume the composer already
saved `output/my-piece/v1/score.json`:

```sh
uv run --no-dev aac validate output/my-piece/v1/score.json
uv run --no-dev aac inspect output/my-piece/v1/score.json
uv run --no-dev aac render output/my-piece/v1/score.json -o output/my-piece/v1/song.wav --report output/my-piece/v1/report.json
uv run --no-dev aac analyze output/my-piece/v1/song.wav
uv run --no-dev aac midi output/my-piece/v1/score.json -o output/my-piece/v1/song.mid
```

Add `--stems output/my-piece/v1/stems` when separate parts help or are requested.
Output paths overwrite existing files; keep score, WAV, MIDI and report distinct.
Success is JSON on stdout and exit 0; failure is JSON on stderr and exit 2. Help
is plain text. Fix `invalid_score` using `issues[].path` and `message`; cross-field
errors may have an empty path. For `operation_failed`, inspect `message` and
`hint`. A passing validator does not guarantee WAV duration or MIDI compatibility.
Use `aac inspect` before rendering to check export readiness and locate blockers
without synthesizing audio. Inspection exits 0 for a valid score even when an
export is blocked; read its `readiness` and structured `issues`, not only the exit code.

Read `warnings`, `gain_applied`, and `wav` peak/RMS/silence/full-scale counts in the
report. Correct unintended silence, clipping, timing errors and inaudible parts.
Attenuation below 1 is not itself a failure; balance gains when it obscures the
intended arrangement. Listen if audio perception is available. Measurements do
not establish musical quality, acoustic realism or a good loop seam.

Use short previews for expensive arrangements, then render the complete requested
piece. Revise when the brief, listening, or diagnostics justify it; do not run an
unbounded optimization loop. For user feedback, preserve the previous version and
edit only what the request warrants. Stop when the requested artifacts are valid
and the stated brief is addressed; report unresolved limitations honestly.

Before rendering a revision, compare the preserved notes or whole tracks with
the original data, plus seed, tempo, cue positions and duration where requested.
Keep track names and unchanged note ordering stable because they affect seeded
excitation. After rendering, check actual duration and any loop seam again. A
revision that preserves score length can still change the WAV length via tails.

## Deliver

Link the actual WAV, MIDI, editable JSON score, render report, and composer source
if one was used. Include a brief musical description, duration, important warnings,
and whether audio was actually auditioned. Keep the score, seed, report and project
lockfile for reproduction. MIDI uses the receiving synthesizer's sounds; it does
not contain these voices, tone controls, automation, effects or audio releases.
Tempo changes and piano pedal CC64 do export; pedal release behavior depends on
the receiver. Stems omit master effects, so their sum differs from a
mix with master processing. Invite concrete revisions such as
“keep the melody, soften the drums, and make the ending longer.” Do not claim a
render was listened to or completed unless it was.

Optional source-tree reading: `docs/site/composition.md` for musical/API examples,
`docs/site/reference.md` for field details, and `docs/agents.md` for CLI integration.
The installed CLI and schema remain the authority if this file was copied alone.
