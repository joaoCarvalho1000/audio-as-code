# Audio as Code

An open-source music framework for creative agents. Compose a soundtrack for a video, game or presentation, render it locally, and keep every note editable.

[Website and demos](https://audioascode.com) · [Source and issues](https://github.com/joaoCarvalho1000/audio-as-code) · [Support the project](https://ko-fi.com/joaothecarvalho)

Give your project a soundtrack: a video reveal, a tiny dragon's boss fight,
or a presentation with an unexpectedly dramatic entrance. Keep the score and code,
then carry the rendered WAV into your video, game or slides. See the
[creative workflow integrations](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/site/integrations.md) for Codex, Claude Code
and Hyperframes recipes.

**Status: 0.1.0 alpha, [available on PyPI](https://pypi.org/project/audio-as-code/0.1.0/).** Python 3.10+, a versioned JSON score, a headless CLI, and an offline synthesis backend. No API keys, audio device, model weights, sample downloads, or DAW are required.

A **score** is the editable recipe for a piece: instruments, notes, timing,
volume and tempo. Write it in Python or JSON; rendering turns it into audio.

```text
Agent / Python program / JSON editor
                 ↓
          Validated score
           ↙           ↘
    Stereo WAV       MIDI file
    + stems          → DAW / synth
       ↓
Signal measurements → agent revises the score
```

The agent makes the musical decisions. This library supplies musical building blocks, synthesis, export, and measurable feedback. It does not call an LLM or generate songs from a text prompt by itself.

The [instrument foundation](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/instrument-foundation.md) organizes the framework around eight musical families and five shared synthesis-engine groups. Instruments are generated from code. Agents can discover what is playable today and inspect the planned catalog:

```sh
uv run aac instruments
uv run aac instruments --all
uv run aac instruments --family plucked_strings
```

The catalog distinguishes available prototypes from planned instruments. It also reports each voice's synthesis engine, supported tone controls, and MIDI mapping.

The catalog now includes **mandolin, kalimba, celesta and recorder**. See their
[models, controls and useful registers](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/extended-instruments.md) before
composing. Every voice is synthesized from code.

The [piano and bowed-string models](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/synthesis.md#piano-and-bowed-strings) use
coupled unison damping and designed excitation/body responses. Their documentation
explains the algorithms and limits; numerical checks do not establish perceptual
realism.

The website pairs five familiar public-domain works with new arrangements by an
AI agent: *Für Elise*, Bach's Cello Suite No. 1 Prelude, Mozart's *Turkish March*,
*Greensleeves* and *Ode to Joy*. **The classic** follows the credited source score;
**Reimagined** changes its musical treatment. Both versions are synthesized from
code and retain editable scores. See the [score credits](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/classic-showcase.md)
and [generator](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/examples/classic_showcase.py) for the source and arrangement scope.
The four [original full compositions](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/examples/full_compositions.py) remain in
the repository as separate examples of form and development.

To browse and audition the catalog, run `uv run python examples/instrument_browser.py`, then open `output/instruments/index.html` directly in your browser. All **49 playable entries** have a famous-music demo, a phrase, and a note/hit preview: **147 clips at 44.1 kHz**, with WAV/MIDI/JSON downloads. [The repertoire](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/music-demos.md) includes Beethoven, Bach, Mozart, and Greensleeves, arranged as solos, small ensembles, and percussion features. Search by instrument, piece, or arrangement, or filter by family. Keep the generated folders beside the HTML file; playback and regeneration need no server or internet connection. The editable page template is `web/instrument-browser.html`. These are procedural prototypes; [model descriptions and limitations](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/orchestra.md) distinguish modal models from spectral approximations.

## Try it

For a coding agent, start with: **“Read https://audioascode.com/llms.txt and add
Audio as Code to this project. Then compose the music in my brief.”**

To add version 0.1.0 to an existing uv project:

```sh
uv add "audio-as-code==0.1.0"
uv run --locked aac instruments
uv run --locked aac schema
```

Commit your project's `uv.lock` to preserve the package and dependency versions.
For a one-off CLI check, run `uvx --from audio-as-code==0.1.0 aac --help`.
The package contains the Python library and CLI. Use a source checkout or the
website's source ZIP for the complete examples, guides and portable skill.

Without uv, create a local environment with `python -m venv .venv`. On Windows,
run `.venv/Scripts/python.exe -m pip install audio-as-code==0.1.0`; on macOS/Linux,
run `.venv/bin/python -m pip install audio-as-code==0.1.0`. Use that interpreter
with `-m audio_as_code --help`; no activation or global installation is needed.

The [quickstart](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/site/quickstart.md)
also covers first compositions and installation from a pinned Git revision.
The standalone source-workspace route follows below.

For complete video, game-loop and presentation examples with exact durations and
verified revisions, see [creative workflows](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/creative-workflows.md).
Piano phrases can use a [sustain pedal](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/piano-sustain.md), including MIDI CC64.
See [render performance](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/render-performance.md) for reproducible benchmarks.

Give the framework to your coding agent, then describe the music. You do not need
to learn Python first; the agent needs local shell access and Python 3.10+.
Download and extract the source ZIP from the website's **Download source** page,
or use this checkout, then paste this into your agent:

```text
Use this Audio as Code source folder. Read skills/audio-as-code/SKILL.md,
set up the local environment, and compose an original 30-second warm, playful
instrumental with electric piano, marimba, bass and light drums. Develop a short
motif and give it a gentle ending. Validate, render and inspect it. Deliver the
WAV, MIDI, editable JSON score, composer source and render report. Tell me
whether you were able to listen to the result.
```

Then ask for a revision: “Keep the melody, make the drums softer, and leave more
space in the second half.” The agent edits the composition and renders a new
version. The [portable skill](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/skills/audio-as-code/SKILL.md) carries the workflow;
the [agent guide](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/agents.md) explains the command contract. Reading this
instruction file works with a shell-capable agent; no vendor plugin integration
is assumed. The renderer does not bundle an AI model or require a provider key.

### Run it yourself

Install Python 3.10+ and [uv](https://docs.astral.sh/uv/), then open a terminal in
this checkout (the directory containing `pyproject.toml`). These commands work
in PowerShell, macOS, and Linux shells; no virtual-environment activation is needed:

```sh
uv sync --locked
uv run aac --version
uv run aac demo -o output/song.json
uv run aac validate output/song.json
uv run aac inspect output/song.json
uv run aac render output/song.json -o output/song.wav --stems output/stems --report output/report.json
uv run aac midi output/song.json -o output/song.mid
uv run aac analyze output/song.wav
```

Open `output/song.wav` in an audio player. The demo is an original eight-bar arrangement with chords, bass, melody, kick, snare, and hi-hat. `uv run python examples/first_light.py` produces the score, WAV, MIDI, stems, and report in one command.

For five contrasting examples, run `uv run python examples/showcase.py`, then open `output/showcase/index.html`. The listening page includes a mellow groove, a dance arrangement, an ambient piece, a chiptune melody, and a five-second audio logo. Each example includes a WAV, MIDI file, editable JSON score, and render report.

For instrument models generated entirely from code, run `uv run python examples/physical_instruments.py` and open `output/physical-instruments/index.html`. It compares the original pluck with a modeled guitar string, followed by marimba and bell examples. All excitations and resonances are generated mathematically; there are no recorded assets.

The first sync downloads dependencies; subsequent rendering is offline. In an
environment with cached dependencies, `uv sync --locked --offline` also works.
Use `uv run aac --help` and `uv run aac render --help` for command options.
Quote paths containing spaces, for example `-o "output/my song.wav"`.

Alternatively, install from this checkout into your own Python virtual environment:

```sh
python -m venv .venv
```

On Windows PowerShell, run `.venv/Scripts/python.exe -m pip install -e .`, then
`.venv/Scripts/python.exe -m audio_as_code --help`. On macOS/Linux, use
`.venv/bin/python -m pip install -e .` and `.venv/bin/python -m audio_as_code --help`.
These paths avoid shell activation and Windows execution-policy changes. This is
a local installation. Explore the listening examples at [audioascode.com](https://audioascode.com).

## Compose in Python

```python
from audio_as_code import Pattern, Song, Track, export_midi, render

melody = Pattern.sequence(["C4", "E4", "G4", None], step=0.5).repeat(4)
kick = Pattern.sequence([36, None], step=1, gate=0.3).repeat(4)

song = Song(
    title="My first loop",
    bpm=110,
    beats=8,
    seed=42,
    tracks=[
        Track(name="Melody", instrument="pluck", notes=melody.notes, gain=0.5),
        Track(name="Kick", instrument="kick", notes=kick.notes, gain=0.7),
    ],
)

song.save("output/loop.json")
report = render(song, "output/loop.wav")
export_midi(song, "output/loop.mid")
print(report["wav"])
```

`Pattern.sequence()` accepts pitches, chords (`["C4", "E4", "G4"]`), and rests (`None`). Use `.repeat(n)`, `.transpose(semitones)`, `.then(other)`, and `.at(beat)` to arrange phrases. Patterns retain trailing rests. `.at()` returns notes positioned on the song's absolute timeline.

Layer a countermelody with `.overlay(other, offset=2)`, expand a motif with
`.stretch(2)`, or soften it with `.scale_velocity(0.7)`. Each returns a new
pattern and preserves the original. See the [composition tools](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/composition-tools.md)
and [runnable example](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/examples/composition_tools.py) for combining these into a piece.

For finer control, construct `Note(pitch="C4", start=0, duration=1, velocity=0.8)` directly. Scores and patterns are immutable; create a revised score from its JSON data when editing.

## Compose in JSON

Agents in any programming language can write this format:

```json
{
  "schema_version": "1",
  "title": "A small phrase",
  "bpm": 120,
  "beats": 4,
  "seed": 7,
  "tracks": [{
    "name": "Lead",
    "instrument": "pluck",
    "gain": 0.6,
    "notes": [
      {"pitch": "C4", "start": 0, "duration": 0.8},
      {"pitch": "E4", "start": 1, "duration": 0.8},
      {"pitch": "G4", "start": 2, "duration": 1.5}
    ]
  }]
}
```

Generate the JSON Schema with `uv run aac schema -o schemas/song-v1.schema.json`. The checked-in schema is derived from the same models used by the renderer. Runtime validation also checks relationships that JSON Schema cannot express, such as unique track names and notes fitting inside a song.

### Musical conventions

| Concept | Meaning |
| --- | --- |
| Time | Quarter-note beats, starting at zero; four beats form a bar in a 4/4 composition |
| Tempo | BPM 20–300; optional ordered step changes in `tempo_map` |
| Pitch | MIDI integer 0–127 or scientific pitch notation; C4 = 60, A4 = 440 Hz |
| Duration | Explicit note length; optional note/track `release_seconds` adds a release after note-off |
| Velocity | Greater than 0 and at most 1; omit a note to make a rest |
| Gain | Linear amplitude, 0–1, per track and master |
| Pan | -1 left, 0 center, 1 right; equal-power stereo panning |
| Song length | Notes fit inside `beats`; automatic release/effect tails extend the WAV |
| Sample rate | 22050, 44100 (default), or 48000 Hz |
| Randomness | Seeded percussion and string excitation; identical score and environment produce identical WAV bytes |

Basic voices: `sine`, `triangle`, `pluck`, `bass`, `pad`, `kick`, `snare`, and `hat`. Drum voices ignore pitch for WAV playback and map to General MIDI notes 36, 38, and 42 on export.

The `guitar`, `marimba`, and `bell` voices add physical/modal approximations. Guitar uses a tuned, damped string loop; marimba and bell use independently decaying resonances. They are simplified instrument models, not calibrated replicas. See [synthesis details](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/synthesis.md).

The rest of the [catalog](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/instrument-foundation.md) is also playable: plucked/bowed strings, four keyboards, woodwinds, brass, drums, tuned percussion, and electronic instruments. New string and percussion voices use modal models. Bowed strings and winds use instrument-specific harmonic source/filter approximations, without nonlinear bow, reed, or bore solvers. See the [orchestra guide](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/orchestra.md) for expression controls and the generated drum kit.

```python
from audio_as_code import Note, Song, Tone, Track, render

song = Song(
    bpm=60,
    beats=4,
    tracks=[
        Track(
            name="Guitar",
            instrument="guitar",
            tone=Tone(brightness=0.6, decay_seconds=3, pluck_position=0.18),
            notes=[Note(pitch="E3", duration=4, velocity=0.75)],
        ),
    ],
)
render(song, "output/string.wav")
```

Brightness and decay work on the modeled decaying voices. Pluck position is available on plucked-string models and harpsichord. Held voices expose selected breath/vibrato controls; `aac instruments` reports each voice's supported settings and defaults. Velocity changes loudness and model brightness. By default notes fade within their score duration. Optional note/track `release_seconds` lets a sound ring after note-off. Ordered `tempo_map` steps, gain/pan automation, and procedural delay/reverb chains add expression; see the [composition guide](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/site/composition.md).

## An agent's working loop

1. Read the schema, discover available voices with `aac instruments`, and choose tempo, harmony, rhythm, and arrangement.
2. Write a JSON score or use the Python API.
3. Run `aac validate`, then `aac inspect` for per-track timing, pitch ranges, polyphony and WAV/MIDI readiness; correct any blockers before rendering.
4. Run `aac render` and inspect the render report and WAV.
5. Adjust notes, timing, orchestration, or gains, then render again.
6. Export MIDI for continued work in a DAW, or deliver WAV and stems.

Every successful CLI operation emits JSON to stdout, including `--version`.
Errors emit JSON to stderr and exit with status 2, with a recovery `hint`.
Help uses normal CLI text. Score inputs are UTF-8 JSON (an optional UTF-8 BOM is
accepted) and are parsed as data; the CLI never executes Python or JavaScript
from a score. See [the agent guide](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/agents.md) for the command contract,
subprocess integration, and limitations.

Reports include a score hash, engine and NumPy versions, duration, peak, RMS, clipping and silence checks, and warnings. **These measurements cannot judge musical quality.** A listening agent or human should audition the rendered audio.

`aac inspect score.json` and Python's `inspect_score(song)` inspect the score
without synthesizing audio or writing files. They report export constraints and
structured issues so an agent can revise before paying the render cost. See the
[inspection contract](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/score-inspection.md); a successful inspection command
can report an export blocker, so check its readiness fields.

## Rendering and export

- WAV: 16-bit stereo PCM, synthesized offline in memory. The prototype limits each render, including release/effect tails, to five minutes. A five-minute render can consume hundreds of MB of RAM; shorter previews are preferable in agent loops.
- Default normalization only reduces gain when the mix exceeds a 0.95 peak ceiling. It never increases a quiet mix. `--no-normalize` preserves mix gain and hard-clips values outside full scale on WAV export; the report exposes this.
- Stems include track gain, pan, master gain, and the same attenuation applied to the mix. They approximately reconstruct the mix within PCM rounding when there are no master effects and no individual stem clips. Stems include track effects but omit master effects, with a warning when the mix uses them. Numeric filenames avoid interpreting track names as paths.
- MIDI: type 1, 480 ticks per quarter note, tempo, track names, programs, volume, and pan. Up to 15 melodic tracks and one track per drum instrument. Overlapping notes of the same pitch on one channel are rejected, including collisions between a drum kit and an individual drum. Quantization can differ from WAV timing by a MIDI tick.
- MIDI instrument sounds depend on the receiver. Drum tracks share channel 10; gain is folded into velocity and per-track drum pan is not exported. MIDI carries tempo changes but does not reproduce the WAV synthesizer, tone controls, automation, effects, audio releases or normalization.
- Reproducibility is scoped to the same software/runtime/platform; floating-point and dependency changes may change bytes. Commit the score and `uv.lock`, and retain the render report.

## Architecture and next steps

`instruments.py` defines the family/engine catalog and voice capabilities. `model.py` defines the portable score contract. `pattern.py` creates notes without coupling composition to playback. `render.py` mixes voices; `physical.py` implements guitar/bar/bell models, `orchestra.py` implements the additional profiles, and `acoustics.py` shares generated noise and analytic body responses. `midi.py` provides an interchange path. `cli.py` makes these capabilities usable from an agent's shell tools.

The framework's instrument direction is sound generated from code. The score is the extension boundary for more detailed physical models. Proposed next steps:

- Named clips and sections, continuous tempo ramps, and arrangement edits.
- Coupled string/body, nonlinear reed/bore, and bow-friction models beyond the current approximations.
- Half-pedaling, instrument articulation switches, and more expression controls.
- An MCP server wrapping the existing validate/render/analyze operations.
- Richer analysis, preview excerpts, and agent-assisted audition workflows.
- Streaming renders, real-time playback, and a browser editor.

These are roadmap items, not implemented features. The 0.1 API may change; score schema changes will use an explicit version.

Related projects worth exploring: [Strudel](https://strudel.cc/), [Sonic Pi](https://sonic-pi.net/), and [SCAMP](https://www.scamp.marcevanstein.com/). This prototype uses its own small score and synthesis implementation; it does not wrap those engines.

## Development

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

See [CONTRIBUTING.md](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/CONTRIBUTING.md), the [architecture guide](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/architecture.md),
[release process](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/releasing.md), [change log](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/CHANGELOG.md), and
[website build and preview guide](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/docs/website.md). For vulnerability handling,
read [SECURITY.md](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/SECURITY.md). Licensed under [MIT](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/LICENSE).

## Support

If Audio as Code helps you make music, you can [support the creator on Ko-fi](https://ko-fi.com/joaothecarvalho). Tips are optional; the framework stays open source.
