# Make your first piece

The quickest route is to give Audio as Code to your coding agent. On the website,
choose **Copy agent prompt**, paste it into the agent, and describe the music.
The copied instructions include the actual source download and portable skill.
Your agent sets up the framework locally and delivers the audio and editable
project. You do not need to learn Python first.

Start with the website's listening pairs: **The classic** follows a credited
public-domain score; **Reimagined** gives it a new arrangement by an AI agent.
Compare the instruments, rhythm and mood, then open the editable scores.
Both versions are synthesized from code. See the
[score credits](classic-showcase.md) and [generator](../music/classic_showcase.py).

For example: "My puzzle game's mushroom shop needs a 20-second cue: curious
marimba, a sleepy bass and one very important bell. Keep the score so we can
change it later." After listening: "Keep the melody, lose half the bells,
and give the ending another second."

The [agent guide](agents.md) explains the handoff and revisions. If you already
have the source, tell your agent to read `skills/audio-as-code/SKILL.md` in that
folder and compose your brief. If it cannot fetch files, use
[Download source](../source.html), extract the ZIP, and give it the folder.

You receive WAV, MIDI, an editable JSON score, composer source when used, and a
render report. The coding agent needs shell access and Python 3.10+. First-time
dependency installation needs network access or cached packages; rendering is
then offline. The framework has no bundled AI model and needs no provider API key.

## Developer route

Prefer to work directly? The rest of this page walks through the same local
framework. Audio as Code synthesizes instruments entirely from code: no recorded
samples or SoundFonts. The website plays pre-rendered examples; Python does not
run in your browser. Install version 0.1.0 from
[PyPI](https://pypi.org/project/audio-as-code/0.1.0/) in your Python project, or use
the [source download](../source.html) for a workspace with the complete examples.

## Add to an existing Python project

From an existing project managed by uv:

```sh
uv add "audio-as-code==0.1.0"
uv run --locked aac --version
uv run --locked aac instruments
uv run --locked aac schema
```

Keep `pyproject.toml` and `uv.lock` with your project. The lock records the package
and dependency versions; `uv run --locked` reuses that environment. To inspect the
CLI without adding a project dependency, use
`uvx --from audio-as-code==0.1.0 aac --help`.

Without uv, create a local environment with `python -m venv .venv`. On Windows,
run `.venv/Scripts/python.exe -m pip install audio-as-code==0.1.0`; on macOS/Linux,
run `.venv/bin/python -m pip install audio-as-code==0.1.0`. No activation is needed.
Use that interpreter with `-m audio_as_code` for the CLI, and to run composer
scripts. For example, on Windows the version command is
`.venv/Scripts/python.exe -m audio_as_code --version`.

To use a specific source revision instead, install Git and run:

```sh
uv add "audio-as-code @ git+https://github.com/joaoCarvalho1000/audio-as-code.git@FULL_COMMIT_SHA"
```

Replace `FULL_COMMIT_SHA` with a verified full commit. Initial installation needs
network access or cached dependencies; rendering afterward is offline.

Give your agent this brief once installed:

```text
Use the Audio as Code dependency in this project. Run uv run --locked aac
instruments and schema to discover its current contract. Compose an original
12-second exploration game loop with marimba, electric piano and bass. Save the
composer and editable JSON score in a fresh output folder. Validate and inspect
export readiness, then render WAV and export MIDI with their reports. Check the
actual duration and loop join. Tell me whether you could listen to it. Keep the
seed, melody and duration fixed when I request a revision.
```

Continue at step 2, using `uv run --locked` before the `aac` and Python commands,
or the local interpreter described above for pip. Save your composer in your project. The
[portable skill](https://github.com/joaoCarvalho1000/audio-as-code/blob/main/skills/audio-as-code/SKILL.md)
has the complete composition and delivery workflow. When using a pinned revision,
read the skill at that same revision; the installed CLI and schema are authoritative.
The installed package contains the Python library and CLI. Use the source workspace
below for bundled tutorial scripts, the portable skill and complete examples.

## 1. Install from the source folder

Open a terminal in the folder that contains `pyproject.toml`.

**With uv (recommended)**

```sh
uv sync --locked
uv run aac --version
uv run aac instruments
```

This uses `uv.lock`, creates a local environment and installs the development
tools. Prefix each command below with `uv run`, for example `uv run aac demo -o
output/song.json` or `uv run python first.py`.

**Without uv**

```sh
python -m venv .venv
```

On Windows, run `.venv/Scripts/python.exe -m pip install -e .`; on macOS/Linux,
run `.venv/bin/python -m pip install -e .`. No activation is necessary. Replace
`aac` below with `.venv/Scripts/python.exe -m audio_as_code` on Windows or
`.venv/bin/python -m audio_as_code` on macOS/Linux. Use that same environment's
Python to run composer scripts.

The install downloads NumPy, Pydantic and mido. Editable installation means source
changes take effect without reinstalling. `aac instruments` returns JSON with
playable IDs, supported controls and model limitations.

## 2. Render the built-in demo

```sh
aac demo -o output/song.json
aac validate output/song.json
aac inspect output/song.json
aac render output/song.json -o output/song.wav --report output/report.json
aac midi output/song.json -o output/song.mid
```

Open `output/song.wav` in an audio player: it is an eight-bar arrangement with
chords, bass, melody and drums. `output/song.mid` takes the notes into a DAW;
`output/song.json` keeps the score editable. The render report records duration
and level checks.

## 3. Write your first score in Python

Save this as `first.py` in your project and run it with the environment's Python
(for example, `uv run --locked python first.py`):

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
print(report["wav"]["duration_seconds"], report["warnings"])
```

What the pieces mean:

- **`beats=8`** is the song length in quarter-note beats: two bars of 4/4. At 110 BPM that is 8 × 60 / 110 ≈ 4.36 seconds. Notes must end by beat 8.
- **`Pattern.sequence(steps, step=0.5)`** places one item per half beat (an eighth note). A string or integer is a pitch, a list is a chord, `None` is a rest.
- **`gate`** is the fraction of each step a note sounds (default 0.8).
- **`.repeat(4)`** repeats the phrase end to end, keeping trailing rests.
- **`seed`** fixes the generated noise in drums and string excitation, so the same score renders the same audio in the same environment.

## 4. Or write the score as JSON

Any language can produce this file. Save it as `output/phrase.json`:

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

```sh
aac validate output/phrase.json
aac render output/phrase.json -o output/phrase.wav
```

If validation fails, its message identifies the score problem to fix before
rendering. The [agent guide](agents.md#errors-and-recovery) explains the full
error format for automated workflows.

## 5. Run the tutorial examples

Six scripts sit next to these pages in `examples/`, starting with [`examples/01_first_score.py`](examples/01_first_score.py). From the source folder they are at `docs/site/examples/`. The first five write to their own folders under `output/docs-examples/`, or to a directory you pass as the first argument. The handoff script takes an input score and a new output directory.

| Script | Teaches | Output length |
| --- | --- | --- |
| [`01_first_score.py`](examples/01_first_score.py) | Patterns, tracks, WAV + MIDI, report | 10 s |
| [`02_motif_and_progression.py`](examples/02_motif_and_progression.py) | Motif transposition, chord voicings, bass line, accents | 18 s |
| [`03_song_form.py`](examples/03_song_form.py) | Sections, dynamics, arrangement density, stems | 89 s |
| [`04_expressive_controls.py`](examples/04_expressive_controls.py) | `Tone` controls, pan, velocity, drum kit pitches | 12 s |
| [`05_agent_loop.py`](examples/05_agent_loop.py) with [`agent-score.json`](examples/agent-score.json) | CLI-only validate → render → revise loop | 10 s per candidate |
| [`06_agent_handoff.py`](examples/06_agent_handoff.py) | Inspect export readiness, render and deliver files to another creative tool | Matches the input score, including tails |

```sh
python docs/site/examples/01_first_score.py
```

Rendering is offline and CPU-bound. On the machine used to write these pages, the 89-second form example took about two minutes; short sketches take seconds.

## Where to go next

- [Composition guide](composition.md): time, pitch, patterns, harmony, form, controls, and mixing.
- [Agent guide](agents.md): a copyable prompt and the exact tool-call loop for AI agents.
- [Reference](reference.md): every CLI command, Python function, score field, and report field.
- [`llms.txt`](../llms.txt): a machine-readable index of these resources.

The project is MIT licensed; see the `LICENSE` file in the source folder.
