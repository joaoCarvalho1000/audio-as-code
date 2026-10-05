# Precise mix revisions for composing agents

The `mixing` helpers added in 0.4.0 edit the existing version 1 score controls and
return a validated, immutable `Song`. They add no buses, instrument sources,
dependencies or score fields. Track names, order, notes, velocities, articulation,
tone, pedal, effects, tempo, seed, duration and instrument/MIDI mappings stay intact.
An edit changes the score hash; preserving musical data does not preserve that hash.

## Inspect, revise and render

```python
from audio_as_code import (
    MixEdit,
    Song,
    apply_mix,
    audition_song,
    inspect_mix,
    render_preview,
)

song = Song.load("score.json")
print(inspect_mix(song))  # Score settings, not audio measurements.
revision = apply_mix(
    song,
    [
        MixEdit(tracks=("Keys", "Guitar"), trim_db=-3),
        MixEdit(tracks=("Keys",), pan=-0.35),
        MixEdit(tracks=("Guitar",), pan=0.35),
        MixEdit(tracks=("Lead",), gain=0.55),
        MixEdit(master=True, trim_db=-1),
    ],
)
revision.song.save("revised.json")
print(revision.report)  # Every target's settings before and after.
report = render_preview(revision.song, "preview.wav", start_seconds=0, duration_seconds=2)
print(report["before_gain"], report["gain_applied"], report["audio"])
audition = audition_song(revision.song, solo=("Lead", "Keys"), mute=("Keys",))
```

`apply_mix(song, edits)` returns `MixResult(song, report)`. A batch applies in order
and fully validates before returning. A later failure leaves the source unchanged.
Empty batches are valid. A group is an explicit tuple/list of exact track names.
Group edits apply once per selected track. Relative dB trims preserve gain ratios;
absolute gain edits set every selected track to the requested level.
To lower accompaniment relative to a lead, trim the accompaniment group and leave
the lead unchanged. This does not estimate how much louder the lead will sound.

Track selection is case-sensitive, preserves whitespace and follows the score's
unique-name rule: `Keys`, `keys` and ` Keys ` can be different tracks. Unknown or
duplicate selections fail; there is no fuzzy matching, instrument selection or
implicit “all” wildcard. In Python, use `tracks=("Lead",)`, not a bare string.
`master=True` is a separate target, so a track named `master` remains selectable.

| Control | Meaning |
| --- | --- |
| `gain=0.5` | Absolute linear amplitude setting, range 0–1. It is about -6.02 dB relative to unity. |
| `trim_db=-3` | Multiply the base gain and every gain automation value by `10 ** (-3 / 20)`. |
| `pan=-0.35` | Absolute pan, range -1 (left) through 0 (center) to 1 (right). |
| `master=True` | Edit `Song.master_gain` and its lane; master pan is unsupported. |
| `replace_automation=True` | Explicitly remove only the automation lanes addressed by absolute gain/pan edits. |

`gain` and `trim_db` are mutually exclusive. Either can accompany `pan` in one
track edit. Numbers must be finite; booleans and numeric strings are rejected.
Boosts are permitted only while **all** resulting base and automated gain values
remain within 0–1, including an inactive base value under an automation lane. A
larger boost raises a clear error; it is never silently clamped. Lower other parts
instead or choose a smaller boost. Zero gain remains zero under any relative trim;
use an absolute level to restore a static silent part. Extremely small trims that
would underflow a nonzero value to zero are rejected; request silence explicitly.

## Preserve automation and musical dynamics

Renderer automation values are absolute and override the static gain/pan for the
entire render; the first and last points hold outside their beat range. A relative
trim therefore scales **every** gain point plus the base gain, preserving point
times, interpolation, fades, swells and zero-valued points. It leaves pan automation
alone. Master trim treats `master_gain` automation the same way. No notes are
revelocitized and no per-note normalization is introduced.

Absolute `gain` or `pan` fails when a matching lane exists, unless the edit includes
`replace_automation=True`. That flag removes only the corresponding lane. For example,
`MixEdit(tracks=("Keys",), pan=-0.3, replace_automation=True)` replaces pan motion
with a fixed position while retaining the volume envelope. To rewrite point shapes
or add new scheduled changes, author the existing `Automation`/`AutomationPoint`
score objects directly.

Track gain precedes track effects. Nonlinear effects such as distortion can react
differently to a trim, so a -3 dB control change need not produce an exact -3 dB
change in the final wet signal. Pan also interacts with stereo effects. Neither
static gain nor pan predicts perceived balance across different voices/registers.

## Audition without losing track identity

`audition_song(song, solo=(), mute=())` makes a disposable score. Nonempty `solo`
includes only its named tracks; empty `solo` includes all. `mute` always wins when
a name appears in both. Excluded tracks retain notes, order, effects and timing,
but their base gain and all gain-lane values become zero. All tracks are allowed
to become silent. Existing master processing remains active.

Keep the original score to restore the mix; there is no hidden mute state or
unmute operation. Never save an audition over the source. Track/note identity and
seeds remain stable, but removing signals can change master effects, peak
attenuation and loudness targeting. An independently normalized solo is not a
level reference for its contribution to the full mix. For that comparison, export
full-mix stems: they retain the mix's common gain and omit master effects. See
[production output](production-output.md). An audition is ordinary score data;
its silence is guaranteed for this audio renderer, not for an external MIDI synth.

## Headless JSON workflow

`aac mix score.json` prints static mix settings. A UTF-8 `edits.json` contains an
ordered array with the same `MixEdit` fields:

```json
[
  {"tracks": ["Keys", "Guitar"], "trim_db": -3},
  {"tracks": ["Keys"], "pan": -0.35},
  {"tracks": ["Guitar"], "pan": 0.35},
  {"master": true, "trim_db": -1}
]
```

```sh
aac mix score.json --edits edits.json -o revised.json --report changes.json
aac mix revised.json --solo Lead --solo Keys --mute Keys -o audition.json
aac preview revised.json -o preview.wav --start 0 --duration 2 --report preview.json
aac analyze preview.wav
```

`--solo` and `--mute` can repeat, and apply after the edit batch. An output score
is required for edits/auditions; input, edits, output and report paths must be
distinct. The complete edit and audition request is validated before any output
is written. Success is one JSON object on stdout, failures are JSON on stderr with
exit status 2. The report's `changes` records the ordered edits; `audition`, when
present, records the subsequent selection and its before/after settings. Top-level
`after` always describes the final score saved. Files are not a multi-file
transaction if a filesystem failure occurs during publication.

Invalid edit objects return `error: "invalid_mix_edits"` with structured issue
paths such as `["edits", 1, "gain"]`. These locations identify entries in the edit
file, rather than incorrectly directing an agent to repair the source score.

Inspection labels its data `score_mix_settings`. `gain_db` describes the static
base gain relative to unity, with `null` for zero. `gain_source="automation"`
means the supplied lane controls the actual level instead; read its points.
`pan_source` likewise distinguishes the static position from a pan lane.
The report includes no invented audio measurements. Render separately to inspect:

- `before_gain.peak_dbfs`: full processed mix peak before output normalization or
  LUFS gain, **after** score master gain and effects.
- `gain_applied`: additional constant output gain. A value below 1 indicates
  attenuation; convert to dB with `20 * log10(gain_applied)`.
- `audio.peak_dbfs`: final sample peak; negate it for sample headroom in dB.
  Silence uses `null`. Check `clipped_samples`, `warnings` and exported `wav` too.

A preview renders the complete score before cropping. `before_gain` and
`gain_applied` retain full-render context; `audio` describes the excerpt. Sample
headroom is not true-peak headroom. RMS is not perceived loudness. Listen before
judging balance; optional LUFS reports are described in the production guide.

## When changing gains is not enough

Short notes on slow-attacking instruments may end before their sustained spectrum
develops. Try a supported `accented` articulation and audition the actual rhythm;
do not infer silence from a lower RMS or solve every onset problem with a boost.
For a very fast run, a plucked or struck voice can be a better arrangement choice.

Measure a quiet part during its entrance and compare it with the accompanying
parts in that section. Whole-song stem energy penalizes short or sparse parts.
Even summed stem-energy percentages do not describe the correlated final mix or
prove that a part is masked. Listen to the dry section, its stems and the wet mix.

Repeated octave/unison doubling can obscure instrumental contrasts. Let one family
carry a phrase, give other families rests or answering phrases, and reserve the
full ensemble for selected arrivals. Reduce accompaniment or reverb before boosting
every quiet instrument. These are arrangement decisions, not automatic calibration.

## Complete reproducible example

```sh
uv run --no-sync python examples/ensemble_mixing.py output/agent-mixing-controls
```

The five-instrument example writes before/after scores and audio, a portable JSON
edit batch, shared-gain stems, a lead/keys audition, a two-second preview, an HTML
listening page and a JSON report of settings, ordered revisions and measured
headroom. It lowers two accompaniment parts by 3 dB while preserving the piano
swell, separates their pan positions, trims the rhythm group, sets a lead level
and applies a small master trim. All sound is generated from code.
