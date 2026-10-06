# Changelog

Audio as Code is an early prototype. Package versions and score schema versions
are separate.

## Unreleased

## 0.4.0 - 2026-10-06

Published on [PyPI](https://pypi.org/project/audio-as-code/0.4.0/).

### Added

- Validated `MixEdit`/`apply_mix` helpers and `aac mix` JSON batches for exact-name
  group gain/pan edits, automation-preserving dB trims, and disposable mute/solo
  auditions. Settings reports distinguish authored controls from audio measurements.
  See `docs/mixing.md` and the complete `examples/ensemble_mixing.py` workflow.

### Changed

- Conservative fixed source-level trims reduce loud sustained and quiet struck/plucked
  outliers across the instrument catalog. Thirteen voices change level; user gains,
  velocity response, register variation and envelopes retain their behavior. Existing
  score IDs are unchanged, but rendered audio and some mix balances intentionally differ.
- Added `examples/instrument_balance.py` for dry register/velocity measurements and
  fixed-gain A/B auditions of all 70 entries and representative arrangements. These
  numerical checks do not establish perceived balance or acoustic realism.

## 0.3.0 — 2026-10-05

Published on [PyPI](https://pypi.org/project/audio-as-code/0.3.0/).

### Added

- 21 generated voices for disco, techno, trance and drum & bass, with explicit
  resonant spectral envelopes, unison, glide, FM and electronic drum controls.
  Catalog descriptions distinguish designed timbres from physical/circuit models.
- Slap/pop/muted bass and muted electric-guitar articulations.
- Resonant filter sweeps, oversampled distortion, stereo chorus, phaser,
  tempo-synced tremolo and beat-triggered ducking in track/master effect chains.
- Four complete dance arrangements of the 16-bar “Ode to Joy” hymn edition,
  alongside its original setting, dry auditions and editable score/MIDI exports.

### Fixed

- Generated attack/breath noise no longer depends on note length or wraps the
  end of a note onto its attack. Noise-sideband filtering uses causal convolution.
- Pulse-width voices now use the centered pulse's correct Fourier phase.
- Basic oscillators taper partials below Nyquist without normalizing away the
  loss of inaudible harmonics. Distortion reconstructs its input with a sinc
  filter before saturation, reducing imaging and preserving treble response.
- Release verification now waits for PyPI's installation index as well as release metadata.

### Changed

- Normal bowed-string and wind notes now use the same separate harmonic/noise
  release laws as articulated notes when `release_seconds` is positive.
- Bell and clavinet use finite strike contact; electronic hats and ride lose
  upper-band energy faster than their lower ringing modes.
- These synthesis refinements intentionally change generated audio from older
  builds. Canonical score IDs are preserved; seeded rendering is repeatable
  within the same engine/runtime. Pin the engine version when reproducing audio.

## 0.2.0 ? 2026-10-04

Published on [PyPI](https://pypi.org/project/audio-as-code/0.2.0/).

### Added

- `aac init` creates an editable composition project from installed wheel resources;
  `aac doctor` checks the active runtime with a short local synthesis probe.
- Tempo-aware timestamp cues, named section replacement and repeated loop previews
  with boundary measurements through the Python arrangement helpers.
- Optional `soft` and `accented` note/track articulations for 13 bowed-string and
  wind voices, with shaped harmonic attacks and releases. Existing unarticulated
  scores retain their deterministic audio and score hashes.
- PCM24 and float32 WAV export, full-context excerpt previews, progress callbacks,
  cooperative cancellation and staged audio publication. CLI progress uses a
  separate JSON Lines file.
- Optional `loudness` extra for BS.1770-4 integrated measurement and constant-gain
  targeting with a sample-peak ceiling. It does not measure or limit true peak.

### Changed

- Documented versioned PyPI installation alongside the source workspace and pinned
  Git routes. These onboarding updates follow the 0.1.0 package release.
- HTML responses allow compression after disabling the Cloudflare RUM injection;
  post-deployment checks still verify that no beacon is added.

## 0.1.0 — 2026-10-03

Initial release on [PyPI](https://pypi.org/project/audio-as-code/0.1.0/).

### Added

- Website sitemap, canonical page URLs, structured project metadata, social
  previews, and full plain-text agent documentation alongside `llms.txt`.

- Piano `PedalEvent`/`Track.pedal` controls, tempo-aware damper gates, tail-aware
  inspection and MIDI CC64 export, with a reproducible dry/pedal comparison.
- Original exact-duration video, game-loop and presentation workflows with
  revisions, measurable preservation contracts and two-cycle loop verification.
- Cloudflare Workers/R2 website staging and streamed large downloads with range
  support; hosting tools are separate from the Python engine.
- Immutable, validated schema-version-1 scores and procedural instrument discovery.
- Seeded offline stereo WAV rendering, stems, MIDI export, and signal reports.
- Tempo changes, gain/pan automation, note releases, generated delay and reverb.
- `Pattern.overlay()`, `stretch()`, and `scale_velocity()` for arranging phrases.
- Read-only `inspect_score()` and `aac inspect` with score facts, tail-aware render
  readiness, MIDI readiness, and structured issues. Inspection does not synthesize
  audio or establish perceptual quality.
- Complete public-domain classic performances with paired new arrangements, source
  credits, editable scores, and repeat-expansion records.
- Portable agent instructions, composition examples, and local listening pages.
- Mandolin, kalimba, celesta and recorder models with discoverable controls,
  approximate MIDI mappings and register-specific auditions: 49 playable voices
  and 147 instrument clips in total.
- Instrument-browser subset generation and validated resume caching, keyed by
  synthesis/generator source, score data, runtime versions and artifact hashes.
- Typed-package marker, distribution inspection and isolated installation checks,
  issue/PR templates, and contribution, architecture, security, and release guides.

### Changed

- The instrument library shares the website's visual style, includes per-voice
  agent handoff snippets and privacy controls, and uses a smaller page payload.
  `instrument_browser.py --html-only` refreshes its page without rerendering audio.
- Automation converts ordered control points in one tempo sweep, avoiding repeated
  scans of dense tempo maps while retaining the same sample values.
- CI actions are pinned; dependency update PRs are scheduled monthly. Hosting
  checks exercise the locked Wrangler installation as well as download behavior.

- Separated voice synthesis and PCM analysis from render orchestration. Shared
  timing, MIDI pitch mapping and export limits keep inspection and exporters
  aligned without changing public imports or seeded output.
- Reuse fixed envelope/harmonic tables across notes, and avoid allocating unused
  oscillator arrays when a physical or modal engine supplies the voice.

- Orchestra coefficient tables and immutable profiles live in a separate private
  module; existing imports and seeded synthesis behavior are preserved.
- Internal planning notes are excluded from Git, source distributions and the
  website source download while public contributor and agent guides remain.

- Synthesis calculations reuse temporary buffers and repeated envelope terms
  without changing the measured seeded float32 output. See the reproducible
  rendering benchmark for workload-specific timings.
- Piano unisons at and above 65 Hz use passive shared bridge damping; the lower
  single-string register retains its existing decay. Bowed-string brightness
  uses absolute-frequency bandwidth and body resonances now include phase.
- Classical reimaginings use the new voices, phrase dynamics and instrument
  contrast while retaining complete source-note coverage. Original classical
  scores keep their notes, timing and instrumentation.
- Instrument auditions use family-specific phrasing, useful registers and
  exposed note attacks/releases. These models remain procedural prototypes;
  numerical checks do not establish perceptual realism.

### Fixed

- Malformed ancillary WAV chunks return the normal structured CLI diagnostic.
- Source downloads reject symlinks and Windows junctions before replacing an
  archive, preventing linked files outside the portable source tree from leaking.
- The agent-loop tutorial reports failed MIDI exports and WAV analysis as failures.
- Instrument-row Pause clicks no longer count as new analytics play requests.

- WAV analysis bounds each PCM read to 256 KiB, preventing untrusted channel
  counts from triggering multi-gigabyte temporary allocations.

- Regenerating only classical reimagination scores invalidates an earlier
  listening manifest, preventing fresh scores from being paired with stale audio.
- MIDI export warnings describe the features present in the score, preserving
  the JSON report shape and exported MIDI bytes.

- Shared path preflight rejects conflicting outputs before CLI or Python rendering
  can overwrite a source or another output.
- Malformed WAV files with a zero sample rate fail with a clear value error and a
  structured CLI diagnostic rather than an uncaught division error.
- Source distributions and wheels exclude local agent state, credentials, logs,
  caches, and generated audio; archive checks enforce the packaging boundary.

### Compatibility and limits

- Python 3.10+; the CI matrix exercises 3.10 and 3.13 on Linux/Windows and 3.13 on
  macOS. The prototype does not promise a stable Python API yet.
- Existing instrument IDs, seeded score behavior, and schema version `"1"` remain.
- The piano and bowed-string refinement intentionally changes their rendered
  audio. The original eleven electronic/physical voices remain unchanged.
- Offline rendering is limited to 300 seconds including releases and effect tails.
  Deterministic rendering is scoped to a fixed software environment.
- Instruments use procedural/physical/modal or source/filter approximations.
  Recorded samples, SoundFonts, and measured impulse responses are not sources.
- MIDI sound depends on the receiving synthesizer; procedural effects, tone
  controls, automation and audio tails do not transfer as equivalent audio.
