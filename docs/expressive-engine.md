# Tempo, automation, effects, and release

Audio as Code supports these optional features in **schema version 1**. Existing
scores retain fixed BPM, within-note fades, and their canonical score hashes when new
fields are left at their defaults. The expanded saved JSON includes new defaults;
the renderer omits those defaults when computing the score hash.

Audio is deterministic for a fixed engine and runtime. Synthesis improvements
can change the sound without changing the score ID; pin the engine version as
well as saving the score when reproducing a render.

Run the complete example:

```sh
uv run python examples/expressive_engine.py
uv run aac validate examples/expressive-score.json
uv run aac render examples/expressive-score.json -o output/expressive.wav --report output/expressive.report.json
uv run aac midi examples/expressive-score.json -o output/expressive.mid
```

The Python example writes a score, WAV, MIDI, three stems and a report under
`output/expressive-engine/`. Its electric piano moves across the stereo field,
changes gain, and feeds five generated echoes. A flute crosses a tempo change.
The final notes release into a generated stereo reverb after the written ending.

## Musical time

`Song.bpm` still sets the initial tempo. Optional `tempo_map` entries contain
`beat` and `bpm`:

```json
"tempo_map": [{"beat": 8, "bpm": 84}, {"beat": 12, "bpm": 126}]
```

These are **step changes**, not ramps. BPM is constant until the next entry.
A change at beat zero overrides the initial BPM. Entries must be strictly ordered,
unique, nonnegative, before `Song.beats`, and use BPM 20–300. At most 1,024 changes
are allowed. All beats are quarter-note beats.

`song.beat_to_seconds(beat)` integrates this map. The renderer uses it for both
ends of each note, automation timing, arrangement duration and release placement.
A note crossing a change stays on for the sum of its segment durations.
`song.seconds` is the written arrangement duration; `song.render_seconds` also
includes release and effect tails. CLI validation reports both durations.

MIDI exports the same step tempo map, including changes at zero. Its 480 ticks
per beat and integer microseconds per beat introduce normal MIDI quantization;
sub-tick changes can share a tick, in score order. WAV timing uses the audio sample
clock. Neither export implements continuous tempo ramps.

## Automation

Track lanes support exactly `gain` and `pan`. Song lanes support exactly
`master_gain`. Each parameter may appear once at its scope. No arbitrary parameter,
expression, plug-in or executable code is evaluated.

```json
"automation": [{
  "parameter": "pan",
  "interpolation": "linear",
  "points": [{"beat": 0, "value": -0.75}, {"beat": 8, "value": 0.75}]
}]
```

A lane replaces the corresponding static value with an **absolute value**.
Gain values range from 0 to 1 and pan from −1 to 1. At least one and at most 1,024
strictly ordered, unique points are required per lane, all within the written
arrangement. The first and last values hold outside the lane's point range,
including release/effect tails. Use a point at beat zero to make the initial value
explicit. Track gain zero is therefore not a mute when an active lane overrides it.

`linear` (default) means linear **in musical beats**, with slopes adjusted at each
tempo change. `step` holds until the next point, changing on the first audio sample
at or after it. Controls are evaluated at every sample; there is no control-rate
stepping. Pan uses equal-power left/right gains. A sharp step can click: use linear
points close together when a smooth transition is desired.

Tone, pitch, note velocity, tempo ramps, effect parameters and effect bypass are
not automatable. MIDI does not export these lanes; its warning explains that it
uses the static gain/pan values.

## Note-off and release

`Track.release_seconds` defaults to zero and accepts 0–10 seconds. An optional
`Note.release_seconds` overrides it; `null` inherits and zero explicitly restores
the original gate for that note. The score's `duration` always describes the held
interval in beats, and must still fit inside `Song.beats`.

With a positive release, the procedural voice continues beyond note-off, multiplied
by a cosine fade that reaches zero at the end of the release. The attack remains
inside the held interval. With zero release, the historical fade remains inside
the written duration. The engine automatically allocates room for notes ending at
the arrangement boundary; trailing rests can already contain a release, in which
case no extra arrangement length is needed.

This is a **renderer envelope**, not a new physical sustain model. Struck/plucked
voices continue their existing natural decay; increasing release cannot revive an
already decayed sound. Held source/filter voices continue their generated source
under the fade. Bow/reed transitions, acoustic room calibration,
and sympathetic-string coupling are not modeled. MIDI keeps written note-offs and leaves
release behavior to the receiving synthesizer.

For supported bowed strings and winds, optional [soft and accented
articulations](articulations.md) additionally change the source's harmonic buildup
and excitation noise. During a positive release, their upper harmonics and noise
decay independently of the fundamental under the same renderer fade. These are
designed source/filter gestures, not a nonlinear bow or bore simulation.

Piano also supports a [binary sustain pedal](piano-sustain.md) through
`Track.pedal`. It extends the gates of keys released while down and exports
MIDI CC64; its damper release can extend the rendered duration. This is separate
from the general release envelope and does not simulate physical pedal mechanics.

## Generated effects

Tracks and songs accept an ordered `effects` array, at most four processors each.
All processors are deterministic, stereo, linear and generated from equations.
They load no recording or measured impulse response and make no room-realism claim.

| Processor | Controls and defaults | Allocated tail |
| --- | --- | --- |
| `delay` | `time_seconds`: 0.01–2 (0.25); `feedback`: 0–0.85 (0.4); `repeats`: integer 1–16 (4); `mix`: 0–1 (0.2) | time × repeats; feedback zero needs only one echo |
| `reverb` | `decay_seconds`: 0.1–5 (1.2); `mix`: 0–1 (0.2) | decay + 0.1 seconds |

```json
"effects": [
  {"type": "delay", "time_seconds": 0.27, "feedback": 0.48, "repeats": 5, "mix": 0.27},
  {"type": "reverb", "decay_seconds": 1.8, "mix": 0.23}
]
```

Delay is a **finite echo train**. Echo 1 has unit wet gain; each following echo is
multiplied by `feedback`. Only `repeats` echoes exist. Delay time is in seconds and
does not follow BPM changes. There is no unbounded feedback loop or ping-pong mode.

Reverb generates four decaying comb responses and two short finite all-pass
diffusers per channel, with different stereo delay lengths. The comb amplitudes
fall nominally 60 dB over `decay_seconds`; the generated response is finite and
fades over its last 10 ms. The setting is an algorithmic decay control, not a
measured room RT60. Block FFT convolution applies this generated response; it does
not load an acoustic impulse-response asset.

For both processors `output = (1 − mix) × dry + mix × wet`. Mix zero bypasses the
processor exactly and adds no tail. Serial chains add their tail budgets. Effects
do not normalize each stage, so echo overlap or resonances can increase peaks.

Signal order is note velocity/release → summed track → track gain/pan automation
→ track effects → master gain automation → track sum → master effects → optional
peak attenuation. Consequently track-gain fades leave existing track echoes audible;
master-gain fades scale track echoes, while existing master reverb can keep ringing.

Stems contain track effects and master gain/automation, and share the final mix's
attenuation. They omit master effects. Their sum therefore differs from a mix with
master effects; the export report warns about this. All stem buffers match the full
render duration. Without master effects their float signals sum to the mix up to
floating-point rounding; exported PCM also has quantization error.

## Limits and reporting

The offline limit remains **300 seconds including all tails**. The renderer
computes the latest note release plus its track chain's tail, at least the written
duration, then appends the master chain's tail. Master effects reserve their tail
even for a silent arrangement. No custom truncation or infinite ringing is supported.
Tail-aware limits are checked before allocating audio or writing WAVs.

The existing 64-track and 100,000-note limits remain. Effects are limited to four
per track/master, delay to 16 echoes, and reverb to 5 seconds. Tracks/stems are
processed sequentially; automation uses 65,536-sample blocks, and reverb uses
overlap-add FFT blocks to avoid an FFT buffer as large as the entire song. Rendering
still holds full stereo mix/track buffers and may be expensive for dense scores or
many processors; this is an offline engine, with no real-time deadline guarantee.

Reports include `score_duration_seconds`, `tail_seconds`, configured `effects`,
post-effect `before_gain` peaks and clipping counts, final audio measurements, and
warnings. Default normalization attenuates peaks above 0.95 and never boosts.
`--no-normalize` returns unclipped float audio internally; 16-bit WAV export clips
out-of-range samples and warns. Stem peaks are checked separately.

These checks establish timing, signal bounds and reproducibility within a fixed
environment. They do not establish perceptual realism or musical quality.
