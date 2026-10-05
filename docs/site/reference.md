# Reference

Audio as Code 0.3.0. Python distribution `audio-as-code`, import `audio_as_code`,
command `aac`. Install `audio-as-code==0.3.0` from PyPI for the engine and CLI;
use the source workspace for the complete examples and portable skill. See the
[quickstart](quickstart.md) for both routes. The 0.2 API may change; breaking score
format changes will use a new `schema_version`. Expression fields are optional
additions to version 1.

Machine-readable versions of this page: the score schema at [`../schemas/song-v1.schema.json`](../schemas/song-v1.schema.json) (same as `aac schema`) and the instrument catalog at [`../instruments.json`](../instruments.json) (same as `aac instruments --all`).

## Command line

```text
aac [-h] [--version] {init,doctor,instruments,demo,schema,validate,inspect,render,preview,midi,analyze} ...
```

Also runnable as `python -m audio_as_code`. With uv, prefix with `uv run`.

| Command | Arguments | Does |
| --- | --- | --- |
| `aac --version` | | Print `{"version": "0.3.0"}` |
| `aac init` | `DIRECTORY` | Create a starter in a new or empty folder; never install dependencies |
| `aac doctor` | | Check the imported runtime and short synthesis path |
| `aac instruments` | `[--all] [--family F] [--engine E]` | Print the catalog. Without `--all`, only playable voices |
| `aac demo` | `[-o OUTPUT]` (default `demo.json`) | Write the built-in demo score |
| `aac schema` | `[-o OUTPUT]` | Print the JSON Schema, or write it to a file |
| `aac validate` | `score` | Check a JSON score; print a summary |
| `aac inspect` | `score` | Inspect tracks and WAV/MIDI readiness without rendering or writing files |
| `aac render` | `score -o OUTPUT [--stems DIRECTORY] [--format pcm16\|pcm24\|float32] [--report REPORT]` | Render stereo WAV; PCM16 by default |
| `aac preview` | `score -o OUTPUT --start SECONDS --duration SECONDS` | Export an excerpt after a full-context render |
| `aac midi` | `score -o OUTPUT` | Export a type-1 MIDI file |
| `aac analyze` | `audio` | Measure 16/24-bit PCM or 32-bit float WAV |

`--family` choices: `plucked_strings`, `bowed_strings`, `keyboards`, `woodwinds`, `brass`, `percussion`, `pitched_percussion`, `electronic`. `--engine` choices: `string`, `air_column`, `modal`, `membrane`, `electronic`.

**Exit status and output.** Success: exit 0, one JSON object on stdout. Failure: exit 2, one JSON object on stderr, either `{"error": "invalid_score", "issues": [{"path", "message", "type"}]}` or `{"error": "operation_failed", "message": "..."}`, optionally with a `hint` string. `-h`/`--help` prints plain text, not JSON.

**Render options.** Both render commands accept `--format`, `--report`,
`--progress-file PATH` (live JSON Lines), and either `--no-normalize` or
`--target-lufs FLOAT`. A target requires `audio-as-code[loudness]`;
`--peak-ceiling-dbfs FLOAT` requires a target and defaults to -1 dBFS. It is a
sample-peak bound, not a true-peak limiter. Preview costs a full render. Read
[production output](production-output.md) for exact semantics.

**Files.** Parent directories are created. Existing outputs are overwritten. The score, WAV, report, progress log, and every stem path (`DIRECTORY/01.wav`, `02.wav`, … in track order) must be distinct.

**Inspection.** `inspect` exits 0 when inspection succeeds, including when the
score cannot be exported. Check `readiness.render.ready` and `readiness.midi.ready`.
Each issue has `code`, `severity`, `target`, `path` and `message`. Only issues with
`severity: "error"` block their export target. Readiness covers static score rules;
it does not test output paths, runtime resources or audio quality. Polyphony counts
written note intervals, including muted notes, and excludes releases and effects.

## Score format (schema version 1)

Unknown fields are rejected everywhere. Numbers must be finite. Times are quarter-note beats.

### Song

| Field | Type | Default | Constraint |
| --- | --- | --- | --- |
| `schema_version` | `"1"` | `"1"` | Only `"1"` |
| `title` | string | `"Untitled"` | 1–200 characters |
| `bpm` | number | 120 | 20–300 |
| `beats` | number | 16 | > 0, ≤ 65536; every note must end by it |
| `sample_rate` | integer | 44100 | 22050, 44100, or 48000 |
| `seed` | integer | 0 | 0–4294967295 |
| `master_gain` | number | 0.8 | 0–1 |
| `tracks` | array of Track | required | 1–64, unique names, ≤ 100,000 notes in total |
| `tempo_map` | array of TempoChange | `[]` | At most 1024; strictly increasing beats before song end |
| `automation` | array of Automation | `[]` | At most one lane, targeting `master_gain` |
| `effects` | array of tagged effects | `[]` | Ordered chain, at most 4 effects; see below |

### Track

| Field | Type | Default | Constraint |
| --- | --- | --- | --- |
| `name` | string | required | 1–80 characters, at least one visible character, unique |
| `instrument` | string | `"pluck"` | A playable catalog ID |
| `gain` | number | 0.6 | 0–1, linear |
| `pan` | number | 0 | −1 (left) to 1 (right), equal-power |
| `tone` | Tone or null | null | Only fields in the instrument's `tone_controls` |
| `articulation` | string or null | null | Only values in the instrument's `articulations`; null selects the default gesture |
| `notes` | array of Note | `[]` | `drum_machine` pitches must be 36, 38, 42, 45, 49, 54, 60, or 64 |
| `release_seconds` | number | 0 | 0–10; inherited by notes without an override |
| `pedal` | array of PedalEvent | `[]` | Piano only when nonempty; at most 1,024 ordered alternating down/up events within the song |
| `automation` | array of Automation | `[]` | At most two lanes; unique `gain`/`pan` targets |
| `effects` | array of Delay or Reverb | `[]` | Ordered chain, at most 4 effects |

`Track.pedal` defaults to `[]` and supports up to 1,024 ordered `PedalEvent`
objects on `piano`. Each has a nonnegative `beat` and strict boolean `down`.
Events alternate down/up, start down and cannot exceed song end. Notes released
under the pedal ring until lift; an open pedal lifts at score end. A default
0.12-second damper release applies to captured notes unless overridden. See the
[pedal timing, release and MIDI rules](../piano-sustain.md).

### Note

| Field | Type | Default | Constraint |
| --- | --- | --- | --- |
| `pitch` | integer or string | `"C4"` | MIDI 0–127, or a name: letter A–G (either case), optional `#` or `b`, octave −1 to 9 (C4 = 60, C-1 = 0) |
| `start` | number | 0 | ≥ 0 |
| `duration` | number | 1 | > 0 |
| `velocity` | number | 0.8 | > 0, ≤ 1 |
| `release_seconds` | number or null | null | 0–10; null inherits the track; zero keeps the original gate |

| `articulation` | string or null | null | Null inherits the track; a supported value overrides it |

Read [articulations](articulations.md) for the 13 supported bowed-string and wind
voices, note inheritance, designed attack/release gestures and MIDI limitations.
For bass/guitar and acid gestures, see [electronic instruments](electronic-instruments.md).

### Tempo, automation, and effects

`TempoChange(beat, bpm)` uses nonnegative beats and BPM 20–300. Changes are steps;
`bpm` applies before the first change, and a change at beat zero overrides it.
Note starts and ends are converted by integrating the tempo segments. Continuous
tempo ramps are not implemented.

`Automation(parameter, points, interpolation="linear")` takes 1–1024
`AutomationPoint(beat, value)` entries with strictly increasing, nonnegative beats
at or before song end. `interpolation` is `"linear"` or `"step"`. Values are
absolute: gain/master_gain 0–1, pan -1–1. Before the first and after the last
point, its endpoint value holds. Linear interpolation follows beats even across
tempo changes. Song lanes only accept `master_gain`; track lanes accept `gain`
and `pan`. Each parameter can appear only once per owner.

| Effect field | Default | Constraint |
| --- | --- | --- |
| Delay `type` | `"delay"` | JSON discriminator |
| Delay `time_seconds` | 0.25 | 0.01–2 |
| Delay `feedback` | 0.4 | 0–0.85; decay between successive echoes |
| Delay `repeats` | 4 | Integer 1–16; finite echo train |
| Delay `mix` | 0.2 | 0–1 dry/wet mix |
| Reverb `type` | `"reverb"` | JSON discriminator |
| Reverb `decay_seconds` | 1.2 | 0.1–5 |
| Reverb `mix` | 0.2 | 0–1 dry/wet mix |

Version 0.3.0 also accepts `Filter`, `Distortion`, `Chorus`, `Phaser`,
`Tremolo` and `Ducker`. See [electronic instruments](electronic-instruments.md)
for exact JSON tags, ranges, timing and limitations.

Effects use generated processing, not measured impulse
responses. Track effects precede master gain; song effects process the summed
mix. Effects and note releases reserve automatic, bounded tails. Releases use a
cosine fade after note-off; zero preserves the old duration-gated sound. Note
on/off positions must still fit within `beats`.

### Tone

| Field | Default | Range |
| --- | --- | --- |
| `brightness` | 0.5 | 0–1 |
| `decay_seconds` | null (catalog default) | 0.1–20 |
| `pluck_position` | null | 0.05–0.45 |
| `breath` | null | 0–1 |
| `vibrato_depth_cents` | null | 0–100 |
| `vibrato_rate_hz` | null | 0.1–12 |
| `glide_semitones` | null | −24–24 |
| `detune_cents` | null | 0–40 |

`null` selects the instrument's default. Which instruments accept which fields is in the [composition guide](composition.md#tone-instrument-specific-controls) and in each catalog entry's `tone_controls`.

## Python API

Everything below is importable from `audio_as_code`.

### Project setup and arrangement

`init_project(path)` and `doctor()` return JSON-compatible dictionaries; see
[project setup](project-setup.md). The setup command uses packaged templates and
does not need the repository.

`beat_at_seconds(song, seconds)` inverts step tempo changes.
`place_at_seconds(song, pattern, seconds)` returns placed notes.
`Arrangement(song, sections)` holds named `Section(name, start_beat, end_beat)`
intervals; `.replace_section(name, {track_name: pattern})` returns a revised
arrangement with the same section length. `LoopRegion(start_beat, end_beat)` and
`render_loop_preview(song, region, repetitions=2)` produce repeated audio and
join measurements. See [arrangement](arrangement.md) for boundary/tail rejection,
note-index reseeding and the difference between repeated audio and continuing
effect state. These helpers do not add fields to score JSON.

### Score models

`Song`, `Track`, `Note`, `Tone`, `TempoChange`, `PedalEvent`, `Automation`, `AutomationPoint`, `Delay`, and `Reverb` are frozen Pydantic models with the fields above. Construct them with keyword arguments or validate data:

| Call | Result |
| --- | --- |
| `Song(...)`, `Song.model_validate(dict)` | Validated song; raises `pydantic.ValidationError` |
| `Song.load(path)` | Read and validate a JSON file |
| `song.save(path)` | Write indented JSON, creating parent directories |
| `song.seconds` | Score duration, integrating the tempo map; `beats * 60 / bpm` without one |
| `song.beat_to_seconds(beat)` | Time at a nonnegative beat; last tempo continues beyond score end |
| `song.render_seconds` | Score duration plus any required release/effect tail |
| `song.model_dump(mode="json")` | Plain data for editing |

`midi_pitch(value) -> int` converts a pitch name or integer to MIDI and raises `ValueError` if invalid.

### Pattern

`Pattern(notes, beats)` is an immutable dataclass. Build one with `Pattern.sequence(steps, *, step=1, gate=0.8, velocity=0.8)` where each step is a pitch, a list or tuple of pitches (a chord), or `None` (a rest). `gate` must be in (0, 1].

| Method | Returns |
| --- | --- |
| `.repeat(times: int)` | `Pattern`, `times` ≥ 1 |
| `.transpose(semitones: int)` | `Pattern` |
| `.then(other: Pattern)` | `Pattern` |
| `.overlay(other: Pattern, *, offset=0)` | `Pattern`; layer at a nonnegative beat offset, retaining all notes and full phrase lengths |
| `.stretch(factor)` | `Pattern`; scale beat timing and length by a positive factor; releases stay in seconds |
| `.scale_velocity(factor)` | `Pattern`; multiply velocities by a positive factor, with every result in (0, 1] |
| `.at(beat: float)` | `tuple[Note, ...]` on the absolute timeline |

### Rendering

| Function | Returns |
| --- | --- |
| `render(song, path, *, normalize=True, stems_dir=None)` | Report `dict`; writes stereo WAV and optional stems (PCM16 by default) |
| `render_audio(song, *, normalize=True)` | Object with `.audio` (float32 array, frames × 2) and `.report`; writes nothing |
| `analyze_wav(path)` | Measurement `dict` for PCM16/24 or float32 WAV |
| `inspect_score(song)` | Static score summary, per-track measurements, export readiness and structured issues; no audio or file writes |
| `export_midi(song, path)` | MIDI summary `dict` |

Renders are limited to 300 seconds including release/effect tails. Default normalization only attenuates the mix to a 0.95 sample peak. A loudness target may boost or attenuate instead. With `normalize=False`, values beyond full scale clip in PCM exports; float32 exports preserve finite overs. Stems contain track processing and master gain/automation, but omit master effects; a warning explains when their sum differs from the processed mix.

All render functions also accept `progress=callback`, `cancel=predicate`,
`target_lufs=None`, and `peak_ceiling_dbfs=-1.0`. File exporters accept
`wav_format="pcm16"`. `render_preview_audio` and `render_preview` require
`start_seconds` and `duration_seconds` and retain full-song processing context.
`RenderProgress` carries stage counts; `RenderCancelled` signals a cooperative
stop. `measure_loudness(audio, sample_rate)` needs the optional loudness extra.
[Production output](production-output.md) specifies gain, metering and publication
behavior; default rendering does not import the optional backend.


### Catalog

| Function | Returns |
| --- | --- |
| `instrument_catalog(*, family=None, engine=None, include_planned=False)` | The `aac instruments` dict |
| `list_instruments(*, family=None, engine=None, include_planned=False)` | Tuple of `InstrumentInfo` |
| `get_instrument(id)` | One `InstrumentInfo`; `ValueError` if unknown |

`InstrumentInfo` fields: `id`, `name`, `family`, `engine`, `status` (`available` or `planned`), `description`, `tone_controls`, `default_decay_seconds`, `midi_program`, `midi_note`, `preview_pitch`, `default_tone`, `articulations`.

## Render report

Returned by `render()` and printed by `aac render`.

| Field | Meaning |
| --- | --- |
| `engine_version`, `numpy_version` | Installed versions used |
| `score_sha256` | Hash of the canonical validated score |
| `title`, `tracks`, `notes`, `seed`, `normalize` | From the score and options |
| `gain_applied` | Mix attenuation, ≤ 1 |
| `score_duration_seconds`, `tail_seconds` | Tempo-integrated score length and additional reserved audio tail |
| `effects` | Master and per-track effect settings |
| `before_gain`, `audio` | Float measurements before and after gain |
| `output`, `wav` | WAV path and measurements of the saved file |
| `stems` | `[{"track", "path", "audio"}]`, empty without stems |
| `warnings` | Human-readable strings |

Float measurements: `sample_rate`, `channels`, `frames`, `duration_seconds`, `peak`, `rms`, `peak_dbfs`, `rms_dbfs` (null when silent), `clipped_samples` (channel samples with |x| ≥ 1), `silent` (exact digital zero). WAV measurements replace `clipped_samples` with `full_scale_samples` (PCM endpoint samples, or float samples with absolute amplitude at least 1). These are signal checks only.

## MIDI export

Piano pedal events export binary sustain CC64 values 127/0 while retaining written
note-on/off times. Pedal changes precede note-offs at the same tick; an open pedal
emits CC64=0 at score end. Damper sound depends on the receiving synthesizer.

Type 1, 480 ticks per quarter note, one tempo track plus one track per score track, with names, General MIDI programs (approximate mappings from the catalog), volume (CC 7 = gain × master gain), and pan (CC 10). Percussion IDs and `drum_machine` share channel 10, and their note events are written into the first percussion track (other percussion track names remain as metadata); drum gain is folded into velocity and drum pan is not exported. Limits: at most 15 melodic tracks, one track per individual drum ID, no note shorter than one tick, and no overlapping notes of the same pitch on a channel (including a kit and an individual drum). Timing can differ from the WAV by up to a tick. MIDI carries step tempo changes on the tick grid but does not carry the synthesizers, `Tone` settings, articulations, automation, effects, note releases, audio tails or normalization; how it sounds depends on the receiver.

## Synthesis scope

All 70 catalog instruments are generated from code across five engine groups: vibrating strings, air columns, bars/bells/plates, membranes, and electronic synthesis. There are no recorded samples, SoundFonts, or measured impulse responses. The models are designed approximations. Bowed strings and winds use harmonic source/filter models without bow-friction or reed/bore physics. Piano supports binary damper-pedal gates; half-pedaling, sympathetic resonance and note-to-note articulations are not modeled. Each catalog `description` states that instrument's scope.

## Reproducibility

Identical score, software versions, and platform produce identical WAV bytes. Each note's generated noise is seeded from the song seed, track name, and note index, so adding a track does not change the others. Keep the score, `uv.lock` (or your installed versions), and the render report together.

## Repository files

| Path in the source folder | Contents |
| --- | --- |
| `src/audio_as_code/` | The library (`model.py`, `pattern.py`, `render.py`, `midi.py`, `instruments.py`, `cli.py`, synthesis modules) |
| `schemas/song-v1.schema.json` | Checked-in score schema |
| `docs/site/` | These pages, `llms.txt`, and the tutorial examples |
| `skills/audio-as-code/SKILL.md` | Portable agent setup, composition and revision workflow |
| `examples/` | Showcase, instrument browser, and other render scripts |
| `LICENSE` | MIT license |
| `CONTRIBUTING.md` | Checks to run before contributing |
