# Make music with your agent

Tell your coding agent what the scene needs: a video reveal, a game cue, or a
presentation entrance with a little too much confidence. Audio as Code gives it
the instruments and renderer. Your agent writes the music, delivers the WAV, and
keeps the score ready for your next change. It needs a local shell, Python 3.10+
and a writable project; you can give direction in ordinary language.

## Start from the website

Use **Copy agent prompt** on the website for a handoff that includes the current
site's exact source download and skill URLs. Paste it into your coding agent,
then add your musical brief. The agent downloads and extracts the source, reads
the bundled [Audio as Code skill](../skills/audio-as-code/SKILL.md), and sets up
its local environment. If your agent cannot download files, use
[Download source](../source.html), extract the ZIP locally, and give it that folder.

The website's previews are real, pre-rendered framework output. Composition and
rendering run locally through the agent's tools. There is no hosted generation
API, MCP server, or browser Python runtime. The framework supplies no AI model
and requires no provider API key; use the coding agent you already have.

The website pairs familiar public-domain music with new agent-written
arrangements. **The classic** follows the credited source score; **Reimagined**
changes its musical treatment. Both are synthesized by this framework and keep
editable scores. The [score credits](classic-showcase.md) identify the historical
works and editions; the [generator](../music/classic_showcase.py) shows the
arrangement code. Use the complete source download to run it. Attribute the
historical composition separately from the new arrangement, and never describe
either render as a sampled recording.

## Add to your project

In an existing uv project, install the released engine and discover its contract:

```sh
uv add "audio-as-code==0.1.0"
uv run --locked aac instruments
uv run --locked aac schema
```

Ask your agent to read [the portable skill](../skills/audio-as-code/SKILL.md), compose
in this environment, and keep the composer and score beside the delivered WAV.
The package contains the engine and CLI. The complete examples and skill file are
in the source project; see the [quickstart](quickstart.md) for pip and Git alternatives.

## Already have the source?

Paste this into your agent in the extracted source folder:

```text
Read skills/audio-as-code/SKILL.md and use this Audio as Code checkout to make
an original 30-second warm, playful instrumental with electric piano, marimba,
bass and light drums. Develop a short motif, vary the second half, and give it
a gentle ending. Set up the local environment, validate, render and inspect.
Deliver WAV, MIDI, editable JSON score, composer source and render report.
Tell me whether you were able to listen to the result.
```

The skill is plain Markdown with portable instructions. An agent can read it
directly; no vendor-specific plugin or automatic skill discovery is required.
Initial installation needs network access or cached dependencies; rendering
then runs offline. Use the downloaded source folder for the bundled examples,
or the versioned package for your own project.

## Describe the music, then revise it

A brief can be as simple as "a quiet, curious 20-second puzzle-game cue with
plucked strings and a clear ending." Add duration, mood, instrument preferences,
or intended use when they matter. The agent can choose key, tempo, harmony and
form. These are also useful starting points:

- "Create a 45-second nocturnal electronic cue with a sparse opening, a stronger
  middle and a resolved ending. Use a recurring three-note idea."
- "Write a six-second bright identity sting for marimba and electric piano.
  Keep it simple, with a memorable final interval."
- "Create a gentle 30-second harp and flute loop for a reading app. Keep the
  texture steady and check the join if you can listen."

After hearing the result, ask for a specific change:

```text
Keep the melody and length. Make the drums softer, leave more space in the
second half, and let the final chord ring longer. Save a new version with
WAV, MIDI, score, source and report so I can compare it with the first.
```

Expect actual file links, a short description, duration and relevant warnings.
MIDI uses your receiving synthesizer's sounds and will not sound identical to the
WAV. All framework voices are procedural approximations. Peak, RMS and clipping
checks cannot tell whether a composition sounds good; the agent must say if it
could not audition the audio.

## The working loop

1. Read the portable skill, locate or install the local package, and discover playable
   voices and score fields through `aac instruments` and `aac schema`.
2. Interpret the brief and compose original material with a motif, development
   appropriate to its length, and an intentional ending or loop seam.
3. Save the score and any composer source; validate and correct reported errors.
4. Render WAV with a report, analyze it, and listen when possible.
5. Revise when the brief or evidence calls for it; preserve earlier candidates.
6. Export MIDI and deliver WAV, score, source, report, and requested stems.

For executable CLI integration, [`05_agent_loop.py`](examples/05_agent_loop.py)
uses [`agent-score.json`](examples/agent-score.json) to demonstrate error recovery
and a measured revision. For musical decisions and Python building blocks, see
[the composition guide](composition.md).

## Tool calls, exactly

Run in the project where the package is installed (see the [quickstart](quickstart.md)). With uv, prefix each command with `uv run --locked`. The environment's `python -m audio_as_code` works wherever `aac` is not on `PATH`.

| Step | Command | stdout on success |
| --- | --- | --- |
| Installed version | `aac --version` | `{"version": "0.1.0"}` |
| Playable voices | `aac instruments` | `catalog_version`, `synthesis_policy`, `families`, `engines`, `instruments`, `counts` |
| One family | `aac instruments --family woodwinds` | Same, filtered |
| One engine | `aac instruments --engine modal` | Same, filtered |
| Include planned | `aac instruments --all` | Same; today all 49 entries are available and `counts.planned` is 0 |
| Schema | `aac schema` or `aac schema -o schema.json` | The JSON Schema, or `{"output": ..., "schema_version": "1"}` |
| Starter score | `aac demo -o demo.json` | `{"output": ..., "title": ...}` |
| Validate | `aac validate score.json` | `valid`, `schema_version`, `title`, `bpm`, `beats`, `duration_seconds`, `render_duration_seconds`, `tracks`, `notes` |
| Inspect the score | `aac inspect score.json` | Track timing, pitch ranges, polyphony, `readiness` and structured `issues`; no synthesis or file writes |
| Render | `aac render score.json -o song.wav --report report.json` | The render report |
| Render + stems | `aac render score.json -o song.wav --stems stems` | Report with a `stems` list |
| Unnormalized | `aac render score.json -o song.wav --no-normalize` | Report; clipped samples are flagged |
| MIDI | `aac midi score.json -o song.mid` | `output`, `tracks`, `ticks_per_beat` (480), `duration_seconds`, `warnings` |
| Measure a WAV | `aac analyze song.wav` | `sample_rate`, `channels`, `frames`, `duration_seconds`, `peak`, `rms`, `peak_dbfs`, `rms_dbfs`, `full_scale_samples`, `silent` |

Output files are overwritten. The score, WAV, report, and stem paths in one command must all be different. Stale files in a reused directory are not removed, so use a fresh directory per candidate.

A typical session:

```sh
aac instruments --family pitched_percussion
aac validate output/agent-run/v1/score.json
aac inspect output/agent-run/v1/score.json
aac render output/agent-run/v1/score.json -o output/agent-run/v1/song.wav --report output/agent-run/v1/report.json
aac analyze output/agent-run/v1/song.wav
```

## A strict score

This is valid as written (`aac validate` prints `"valid": true`). This example uses the basic fields; `sample_rate`, `seed`, `master_gain`, `pan`, `velocity`, and `tone` are optional. Optional `tempo_map`, `automation`, `effects` and note/track `release_seconds` are documented in the [reference](reference.md).

```json
{
  "schema_version": "1",
  "title": "Two bars",
  "bpm": 100,
  "beats": 8,
  "sample_rate": 44100,
  "seed": 5,
  "master_gain": 0.8,
  "tracks": [
    {
      "name": "Keys",
      "instrument": "electric_piano",
      "gain": 0.4,
      "pan": -0.2,
      "tone": {"brightness": 0.4, "decay_seconds": 3},
      "notes": [
        {"pitch": "A3", "start": 0, "duration": 3.9, "velocity": 0.6},
        {"pitch": "C4", "start": 0, "duration": 3.9, "velocity": 0.6},
        {"pitch": "E4", "start": 0, "duration": 3.9, "velocity": 0.6},
        {"pitch": "G3", "start": 4, "duration": 4, "velocity": 0.6},
        {"pitch": "B3", "start": 4, "duration": 4, "velocity": 0.6},
        {"pitch": "D4", "start": 4, "duration": 4, "velocity": 0.6}
      ]
    },
    {
      "name": "Bass",
      "instrument": "bass_guitar",
      "gain": 0.7,
      "notes": [
        {"pitch": "A1", "start": 0, "duration": 3.5, "velocity": 0.85},
        {"pitch": "G1", "start": 4, "duration": 3.5, "velocity": 0.85}
      ]
    },
    {
      "name": "Kit",
      "instrument": "drum_machine",
      "gain": 0.5,
      "notes": [
        {"pitch": 36, "start": 0, "duration": 0.4},
        {"pitch": 38, "start": 2, "duration": 0.3, "velocity": 0.7},
        {"pitch": 36, "start": 4, "duration": 0.4},
        {"pitch": 38, "start": 6, "duration": 0.3, "velocity": 0.7}
      ]
    }
  ]
}
```

Rules the JSON Schema cannot express, enforced by `aac validate`: unique track names, notes ending inside `beats`, tone fields supported by the chosen instrument, `drum_machine` pitches from the kit map, and at most 100,000 notes.

## Reading the render report

| Field | What to do with it |
| --- | --- |
| `warnings` | Act on each. Possible messages: silent render, mix attenuated, mix exceeds full scale (with `--no-normalize`), notes too short for the sample grid, a clipped stem |
| `gain_applied` | 1 means untouched. Below 1, the mix peaked above 0.95 and was turned down; multiply your `master_gain` by about this value |
| `score_duration_seconds`, `tail_seconds` | Score duration and reserved release/effect tail; their total must fit the 300-second render limit |
| `before_gain` | Float mix measurements before that attenuation |
| `audio` | Float measurements after attenuation: `peak`, `rms`, `peak_dbfs`, `rms_dbfs`, `clipped_samples`, `silent`, `duration_seconds` |
| `wav` | The same measurements read back from the saved 16-bit file, with `full_scale_samples` |
| `stems` | One entry per track: `track`, `path`, `audio` measurements. A near-zero stem RMS means that part is inaudible |
| `score_sha256`, `seed`, `engine_version`, `numpy_version` | Keep these to reproduce the render |

`peak_dbfs` and `rms_dbfs` are `null` for digital silence. A low RMS or a high peak is not a musical error by itself. None of these numbers measure realism, taste, or whether the piece works. If your environment cannot play audio, say so in your result instead of implying you listened.

## Errors and recovery

| stderr `error` | Typical cause | Recovery |
| --- | --- | --- |
| `invalid_score` | Malformed JSON (`type` `json_invalid`), field out of range, unknown instrument, unsupported tone field, note past the end | Read each item in `issues`: `path` points into the JSON, `message` says why. Fix and validate again |
| `operation_failed` | Missing file, bad command arguments, render over 300 s, MIDI limits, duplicate paths, unreadable WAV | Read `message`; shorten, split, rename paths, or fix the file |

```json
{"error": "invalid_score", "issues": [{"path": [], "message": "Value error, track 'Lead', note 9: ends at beat 20.5; song ends at 16.0", "type": "value_error"}]}
```

Error objects may also carry a `hint` string with a suggested next step; treat it as advice, and key your logic on `error`, `issues`, and `message`.

Things worth knowing when you parse issues:

- Cross-field problems (a note past the end, duplicate names) have an empty `path`. The track and note index are in the message.
- A track that fails validation can also produce a second issue, `["tracks"]` "Tuple should have at least 1 item after validation". Fix the first issue; the second goes away.
- `validate` passing does not guarantee every backend accepts the score. Rendering fails over 300 seconds including release/effect tails. MIDI export fails with more than 15 melodic tracks, two tracks of the same drum ID, notes shorter than one MIDI tick (1/480 beat), or overlapping same-pitch notes on one channel. Shorten or split the notes, or merge drum parts into one `drum_machine` track.

## Limits to plan around

- Tempo changes are ordered steps; there are no continuous tempo ramps, meter/swing fields, sections, clips or instrument articulation switches. Piano supports binary `Track.pedal` events; see the [pedal rules](../piano-sustain.md) before targeting an exact duration.
- Track gain/pan and song master gain support linear/step automation. Delay and generated reverb can run on tracks or the master; optional note releases extend past note-off. MIDI exports tempo changes but omits these audio controls. Stems omit master effects.
- Tone controls are per track. Use another track for another articulation.
- 1–64 tracks, up to 100,000 notes, `beats` up to 65,536, WAV renders up to 300 seconds including tails. Long renders use hundreds of MB of RAM; keep iteration renders short.
- Rendering is offline and takes real CPU time; orchestral voices are slower than the electronic ones.
- Instruments are code-generated approximations. Do not describe them as recordings or as indistinguishable from acoustic instruments.
- Renders are deterministic for the same score and environment, not across every NumPy version or platform.

## Python instead of the CLI

An agent that can run Python can use the same operations in-process:

```python
from audio_as_code import Song, analyze_wav, instrument_catalog, render

catalog = instrument_catalog()  # same data as `aac instruments`
song = Song.load("output/agent-run/v1/score.json")  # raises pydantic.ValidationError
report = render(song, "output/agent-run/v1/song.wav")
print(report["gain_applied"], report["warnings"], analyze_wav(report["output"])["rms"])
```

See the [reference](reference.md) for every function, and the [composition guide](composition.md) for musical techniques.
