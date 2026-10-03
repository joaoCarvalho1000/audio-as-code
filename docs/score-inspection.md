# Inspect a score before rendering

`aac inspect` reads and validates a score, then reports its arrangement and static
WAV/MIDI export readiness. It does not synthesize audio, export MIDI, write files,
use an audio device, or contact a service.

From the checkout root after `uv sync --locked`:

```powershell
uv run aac demo -o output/inspection-demo.json
uv run aac inspect output/inspection-demo.json
uv run python -m audio_as_code inspect output/inspection-demo.json
```

Both entry points emit the same single JSON document. A valid score returns exit
0 even if an export is blocked. Agents must check `readiness.render.ready` or
`readiness.midi.ready` before choosing their next operation. Invalid scores keep
the existing CLI contract: exit 2, no stdout, and JSON on stderr with
`error: "invalid_score"` and structured `issues[].path`. Missing input files and
invalid command arguments return `error: "operation_failed"`.

The Python API takes a `Song`:

```python
import json
from audio_as_code import Note, Song, Track, inspect_score

song = Song(tracks=[Track(name="Lead", notes=[Note(pitch="A4")])])
report = inspect_score(song)
print(json.dumps(report, indent=2, allow_nan=False))
assert report["validation"]["valid"]
assert report["readiness"]["render"]["ready"]
```

The result contains only JSON values and is deterministic for the same score and
engine version. Inspection revalidates the model, including unchecked Pydantic
copies, and never mutates it. Invalid Python models raise `ValidationError`.

## Report contract, version 1

| Field | Meaning |
| --- | --- |
| `inspection_version` | Report format version, currently `"1"`; independent of the score schema. |
| `validation` | `valid: true` and the validated `schema_version`. |
| `summary` | Title, initial BPM, beats, sample rate, seed, track/note counts, maximum written-note polyphony, score duration, render duration, and tail duration. |
| `tracks` | Input-ordered per-track identity, instrument/family/engine, catalog description, note count, written and mapped MIDI pitch ranges, timing, tail horizons, polyphony, and MIDI percussion status. |
| `readiness.render` | `ready`, `duration_limit_seconds` (300), and rounded output `frames`. |
| `readiness.midi` | `ready`, `melodic_tracks`, `melodic_track_limit` (15), and `ticks_per_beat` (480). |
| `issues` | Deterministically ordered findings, each with `code`, `severity`, `target`, `path`, and `message`. |
| `limitations` | Explicit limits of static inspection and MIDI fidelity. |

Each track has `index`, `name`, `instrument`, `family`, `engine`,
`instrument_description`, `note_count`, `written_pitch_range`, `midi_pitch_range`,
`first_note_beat`, `last_note_end_beat`, `first_note_seconds`,
`last_note_end_seconds`, `dry_end_seconds`, `effect_end_seconds`,
`max_note_polyphony`, and `midi_percussion`.

Pitch ranges contain `{ "min": 60, "max": 69 }` with MIDI integers; empty tracks
have null ranges and null first/last note times. Written pitch is the score's pitch
converted to a MIDI integer, not a measured frequency. Fixed percussion voices
map their written pitches to a single MIDI drum note. `drum_machine` keeps each
note's kit selection. The family name alone does not determine whether a track
uses MIDI channel 10: pitched percussion such as marimba uses a melodic channel.

Times in seconds integrate the score's tempo map. `dry_end_seconds` is the last
written note end plus its effective release, or zero for an empty track.
`effect_end_seconds` adds the track's declared effect tail. These are absolute
horizons from score start, not measured sound durations. Song render duration
follows the renderer's allocation rules, including track and master effect tails;
an empty track can still contribute a declared effect horizon.

Polyphony counts half-open written intervals `[start, end)`. Adjacent notes do not
overlap. Muted notes count; release tails and effects do not. This describes the
arrangement, not CPU load, voice limits, or how many sounds will be audible.

## Stable finding codes

`severity: "error"` means the associated export's static check failed. It does
not mean score schema validation failed. Warnings never change readiness.
`target` is `render`, `midi`, or `score`; `path` is a list of score field names and
zero-based array indices. An empty path denotes the whole score. Agents should
branch on codes and fields, not human-readable messages.

| Code | Severity | Meaning |
| --- | --- | --- |
| `render_duration_limit` | error | Render duration including releases and effects exceeds 300 seconds. |
| `render_below_one_sample` | error | Render duration rounds to zero output samples. |
| `render_note_below_sample` | warning | A note's held duration rounds to zero samples and the renderer skips it. |
| `midi_melodic_channel_limit` | error | More than 15 melodic tracks, including empty or muted tracks. |
| `midi_duration_out_of_range` | error | Song duration is outside the exporter's MIDI tick range. |
| `midi_duplicate_drum_instrument` | error | More than one track uses the same drum instrument ID. |
| `midi_note_below_tick` | error | A note has no positive duration after tick rounding. |
| `midi_same_pitch_overlap` | error | Notes on one track overlap at the same mapped MIDI pitch. |
| `midi_percussion_pitch_overlap` | error | Active percussion notes on different tracks overlap at the same mapped pitch on channel 10. |
| `midi_shared_percussion_channel` | warning | Percussion events share channel 10 and are grouped; gain uses velocity and per-track pan is omitted. |
| `midi_note_timing_quantized` | warning | Some written note boundaries move on the MIDI tick grid. |
| `midi_tempo_timing_quantized` | warning | Some tempo-change positions move on the MIDI tick grid. |
| `midi_tone_not_exported` | warning | Declared tone controls are omitted. |
| `midi_releases_not_exported` | warning | Declared releases and audio tails are omitted. |
| `midi_automation_not_exported` | warning | Automation is omitted; MIDI uses static gain and pan. |
| `midi_effects_not_exported` | warning | Declared procedural effects are omitted. |
| `empty_track` | warning | A track contains no notes. |

Distinct drum instruments can coexist on channel 10. A kit and a dedicated drum
track can also coexist if their mapped notes do not overlap. Cross-track drum
collision checks omit tracks muted by static track/master gain, matching MIDI
export. Within-track overlap checks and duplicate-instrument checks still apply
to muted tracks, as they do in the exporter.

## What readiness establishes

`aac validate` answers whether the score follows the schema and arrangement
rules. Inspection additionally checks the known static duration and MIDI export
constraints. A 301-second score may therefore validate successfully but report
`readiness.render.ready: false` while remaining eligible for MIDI export.

Readiness does not guarantee sufficient memory, writable output paths, successful
runtime synthesis, or any perceptual result. It performs no loudness, clipping,
tuning, musical-quality, or realism measurement. Instrument descriptions come
from the catalog and describe synthesis approximations. MIDI sound depends on
the receiving synthesizer. Render, analyze, and audition an actual WAV when those
properties matter.
