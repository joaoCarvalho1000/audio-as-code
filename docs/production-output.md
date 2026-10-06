# Production output

## Instrument and mix balance

Version 0.4.0 applies conservative fixed source trims to thirteen loud or
quiet catalog outliers. They are internal synthesis coefficients, independent of
pitch, velocity, duration and seed; no note is normalized to its own peak or RMS.
All other voices retain their designed levels. User track/master gain, gain
automation, envelopes and velocity-dependent timbre still work as before.
Existing score IDs stay unchanged, but audio levels and relative mix balance can
change; pin the engine revision when reproducing a render.

This is partial calibration, not equal perceived loudness. Short percussion,
plucked attacks and sub-bass have different musical roles and crest factors.
Arrange with track gains, then use master attenuation or optional LUFS targeting
for delivery. One master gain cannot repair an instrument imbalance. Tone changes,
effects, polyphony and extreme registers can still require additional headroom.

[Precise mix revisions](mixing.md) covers Python/JSON group trims, pan, auditions
and measured preview checks. These controls require Audio as Code 0.4.0 or later;
run `aac --version` to check your installed engine.

Contributors can reproduce the dry audit before and after a synthesis change:

```sh
uv run --no-sync python examples/instrument_balance.py --label before
# Apply the synthesis change, then:
uv run --no-sync python examples/instrument_balance.py --label after --compare before
```

The ignored `output/instrument-balance/index.html` provides fixed-gain A/B files;
each run also writes a JSON report. The audit covers low/middle/high useful
registers at velocities 0.35, 0.65 and 1.0, fixed percussion pitches, and every
drum-machine route. It uses one-second notes at 44.1 kHz, active 20 ms RMS windows
(30 dB below the strongest window, with an absolute -60 dBFS floor), onset RMS,
sample peak, crest factor and six mixes with individual stem measurements.
Add `--loudness` when the optional extra is installed; LUFS is supplementary,
especially for short percussion and low bass. This bounded default-tone audit is
not an exhaustive control, articulation or register sweep. Listen to the exported
comparisons before judging perceived balance; numbers alone cannot establish it.

Preview levels also depend on their scores and export settings. The instrument
browser uses authored gains and peak-only attenuation, with one shared player
volume; its scaled waveforms are not level meters. Electronic-music auditions
normally request -18 LUFS. Neither is a uniform dry instrument-level reference.

## Export controls

From an installed project, use the same options through the CLI:

```sh
aac render score.json -o mix.wav --format pcm24 --progress-file progress.jsonl
aac preview score.json -o excerpt.wav --start 12 --duration 8 --format float32
aac render score.json -o loudness.wav --target-lufs -18 --peak-ceiling-dbfs -1
```

The last command requires the optional loudness extra below. `--progress-file`
keeps stage events in a separate UTF-8 JSON Lines file while stdout contains one
final JSON result. The log can be partial if rendering fails or is interrupted.
Score, audio, report, progress and stem paths must be distinct. Ctrl+C returns a
structured error with exit status 2.

`render(song, path)` still writes deterministic stereo 16-bit PCM WAV with the
existing peak attenuation and report. Choose another encoding explicitly:

```python
from audio_as_code import render, render_preview

render(song, "output/mix-24.wav", wav_format="pcm24", stems_dir="output/stems-24")
render(song, "output/mix-float.wav", wav_format="float32", normalize=False)
render_preview(song, "output/excerpt.wav", start_seconds=12, duration_seconds=8, wav_format="pcm24")
```

`pcm24` uses signed packed 24-bit PCM. `float32` uses IEEE 32-bit floating-point
WAV and preserves finite samples above full scale when normalization is disabled.
PCM encodings round samples and clip at their integer limits; no dither is added.
Higher bit depth does not change the synthesis model or create acoustic realism.
Stems use the selected encoding and the mix's gain. As before, master effects are
omitted from stems, so their sum can differ from the processed mix.

`analyze_wav(path)` accepts the emitted 16/24-bit PCM and 32-bit float RIFF/WAVE
formats. It reads bounded blocks and rejects malformed frames and non-finite
float samples. `peak` is sample peak and `rms` is signal RMS. Neither is a
true-peak or integrated-loudness measurement. `full_scale_samples` counts PCM
samples at the integer endpoints; for float it counts samples with absolute
amplitude at least 1, which does not mean the float file was clipped. Nondefault
formats add `wav_format` to the analysis and export reports.

## Optional integrated loudness

Install `pip install "audio-as-code[loudness]"` (or `uv sync --extra loudness` in
a checkout). Ordinary rendering and WAV analysis do not import the optional
backend. All four render functions accept the same loudness options:

```python
report = render(
    song, "output/mix-loudness.wav", wav_format="pcm24", target_lufs=-18, peak_ceiling_dbfs=-1
)
print(report["loudness"]["achieved_lufs"])
```

`target_lufs` replaces the default peak-only attenuation with one constant gain;
it can boost or attenuate. The range is -70 to 0 LUFS. The sample-peak ceiling
defaults to -1 dBFS and accepts -60 to 0 dBFS. It limits gain across the complete
mix, without a compressor or limiter. A high-crest-factor mix can therefore fall
short of the loudness target. `normalize=False` cannot be combined with a target,
and a nondefault ceiling requires a target. Stems share the mix's gain; individual
stems are not separately normalized or guaranteed to meet the mix's ceiling.

`audio_as_code.loudness.measure_loudness(audio, sample_rate)` accepts finite
floating-point mono or stereo NumPy arrays within float32's numeric range,
0.4 to 300 seconds long, at 22050,
44100, or 48000 Hz. It uses pyloudnorm's DeMan filters and BS.1770-4 integrated
gating: complete 400 ms windows, 100 ms hops, an absolute -70 LUFS gate, and a
relative gate 10 LU below the absolute-gated result. A final incomplete window
is excluded; `measured_frames` and `trailing_frames_ignored` describe that boundary.
No audio samples are removed from the render. See the
[backend documentation](https://github.com/csteinmetz1/pyloudnorm) and
[BS.1770-4, Annex 1](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-4-201510-S!!PDF-E.pdf).

The optional `loudness` report records the backend/version, before/achieved LUFS,
requested/applied gain, target, sample-peak ceiling, and whether the peak bound
limited gain. `target_reached` means the achieved measurement is within 0.1 LU;
it is measured again after gain because gating can change. Silence and fully
gated audio produce `null` LUFS and receive no loudness boost. Warnings stay in
the report. Measurement is before encoding; PCM rounding can change the file's
loudness and sample peak slightly. Preview loudness describes the full render,
including when the excerpt is shorter than 400 ms.

This feature does not measure or constrain true peak, intersample overs, loudness
range, or platform delivery compliance. The checks against FFmpeg's
[ebur128 filter](https://ffmpeg.org/ffmpeg-filters.html#ebur128) cover generated
signals and music; they are not meter certification or perceptual validation.

## Exact excerpts

`render_preview_audio(song, start_seconds=..., duration_seconds=...)` returns a
`RenderResult`; `render_preview` writes its audio. Both render the complete song
and then crop. This preserves original note seeds, tempo, sustained notes,
automation, earlier effect input, and full-mix gain. It costs a complete render
and retains the 300-second limit including effect tails. It is not a streaming
or faster renderer.

Boundaries use `round(seconds * sample_rate)` and the end is exclusive. The end
is clamped to the rendered duration, including tails. Empty excerpts, negative
starts, non-finite bounds, and starts at or after the end are rejected. No fade is
added to cuts; a boundary through a waveform can click.

The preview report's `audio` and `wav` describe the excerpt. Score identity,
`before_gain`, warnings, and `gain_applied` retain full-render context.
`preview.context_audio` describes the full processed mix, and `preview` records
requested seconds and actual frame boundaries.

## Progress and cancellation

All four render functions accept `progress=callback` and `cancel=predicate`.
Callbacks run synchronously; the engine does not print progress. A callback
receives immutable `RenderProgress(phase, completed, total, track)` values with
stage-local counts. Phases include `tracks`, `notes`, `track_effects`,
`master_effects`, `analysis`, `loudness` (when requested), and `export`. Counts are
not wall-clock estimates.

```python
from threading import Event
from audio_as_code import RenderCancelled, render

stop = Event()
try:
    report = render(
        song,
        "output/mix.wav",
        cancel=stop.is_set,
        progress=lambda event: print(event.phase, event.completed, event.total),
    )
except RenderCancelled:
    print("Cancelled")
```

Cancellation is cooperative between notes and processing stages. An individual
voice, effect, measurement, or encoding operation runs to its next checkpoint.
Callers can set `stop` from another thread. Callback exceptions propagate.

Exports prepare all mix/stem files before replacing destinations. Cancellation,
callback errors, and synthesis/encoding failures before publication leave existing
files intact and remove temporary WAVs; newly created directories may remain.
Each final file replacement is atomic, but the group is not a filesystem
transaction: a filesystem failure during publication can replace only part of a
stem set. Cancellation is not checked during that short replacement loop.
