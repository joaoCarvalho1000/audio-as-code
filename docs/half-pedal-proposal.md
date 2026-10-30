# Half-pedal contract proposal and damping experiment

Availability: Unreleased source API, absent from published PyPI 0.5.0. Use a
repository checkout or source ZIP containing `audio_as_code.experimental_pedal`
under `src/` and run `uv sync --locked` from its root. Installing
`audio-as-code==0.5.0` from PyPI alone does not provide this experiment.

Status: experiment for evaluation, not a version 1 score feature. The public JSON
schema and standard MIDI export still support only binary `Track.pedal`. No
existing score ID, binary pedal rendering or catalog control is changed. Do not
put `depth` in a version 1 score: validation rejects it.

## Proposed future contract

An eventual additive track field, `pedal_depth`, would contain strictly increasing
`{beat, depth}` events, with finite depth in 0..1 and at most 1,024 events. Zero
means lifted, one means fully held. It would be mutually exclusive with binary
`pedal`. Omitting it would retain the current synthesis path and canonical score
hash; binary scores would require no migration. New scores would need a renderer
that advertises the control. This proposal is not a finalized schema change.

The initial state is zero. Events are steps, applied before key release and
note-on at the same beat, using the tempo map and rounded sample positions. A
held key is unaffected by the pedal. After its written release the voice loses
energy at a rate determined by current depth, never recovering energy when depth
increases. Several smaller steps permit a gradual release. At song end depth
becomes zero and the final damper tail lasts at most 0.25 seconds. Repeated notes
retain independent voices. Cross-note sympathetic resonance, shared strings,
pedal noise and accurate damper contact physics are outside this first experiment.

MIDI would quantize depth to `round(depth*127)` on CC64 at 480 ticks per beat,
with a final zero at song end. Pedal changes precede key releases and attacks at
the same tick; distinct events can collapse onto one tick, preserving their
order. Inspection/export would warn about both timing/value quantization and
receivers that threshold CC64 as a switch. A receiver is never expected to
reproduce this WAV's envelope or timbre. These CC64 values are reported as a
proposal by the experiment; standard `export_midi` does not export its sidecar.

## Run the bounded prototype

```sh
uv run python examples/pending_audio_experiments.py output/audio-experiments/v1
```

This writes a dry piano score, lifted/half/held WAV comparisons with repeated
notes, depth sidecars and numerical reports, plus the loop examples described in
[arrangement](arrangement.md). Use a new output directory for every candidate.
The listening record starts blank and must be completed by a named listener in
a stated playback environment. No auditory quality claim follows from the tests.

The Python API lives in `audio_as_code.experimental_pedal`: pass a dry, single
piano-track `Song` and a tuple of `PedalDepth(beat, depth)` values to
`render_pedal_depth`. Effects, automation, mastering, binary pedal and explicit
release controls are rejected to avoid ambiguous interactions. It returns
stereo audio and a report. Depth is sidecar data and is not saved by `Song.save`.
Retain the report's events alongside the base score to reproduce the experiment.

This prototype applies an envelope with decay rate `60*(1-depth)**2` per second
after each key release, in addition to the generated piano's natural decay. A
later pedal press cannot restore energy already lost. It lifts automatically at
song end, tapers the bounded tail, and only attenuates peaks above 0.95. Rendering
including the final tail is limited to 300 seconds; event count is bounded and
each voice is accumulated independently. The existing score renderer is untouched.
The coefficients are designed approximations, not measurements of a real piano.

Before promoting this experiment to a serialized control, review the proposed
contract, obtain listening comparisons, decide release-control interactions and
implement matching schema, inspection and actual MIDI export. Issue #4 remains
open until these gaps and its auditory acceptance criteria are satisfied.
