# Instruments generated from code

The instrument direction is procedural synthesis and physical modeling. Every waveform, excitation, and resonance is computed locally. The implementation loads no recordings, sample libraries, or recorded impulse responses. It uses the existing NumPy dependency.

The [instrument foundation](instrument-foundation.md) defines the musical families, shared engines, and catalog contract. Use `aac instruments` to discover available models and controls, or `aac instruments --all` to inspect planned instruments. The modal engine's marimba and bell profiles share the same resonance implementation.

## Original physical/modal models

This page documents the original guitar, marimba, and bell algorithms. The [orchestra guide](orchestra.md) documents the additional playable strings, keyboards, winds, brass, percussion, and electronic models. Their algorithms and limitations differ from these three models.

| Voice | Algorithm | What is approximated |
| --- | --- | --- |
| `guitar` | Karplus-Strong style damped delay loop, with fractional-delay tuning | Energy circulating along a plucked string, losing upper harmonics over time |
| `marimba` | Damped modal synthesis | A struck wooden bar with mode ratios 1, 4, 10, and 17 |
| `bell` | Damped modal synthesis | A designed metallic chime with inharmonic resonances |

These are simplified models. The guitar drives a generated damped-mode body filter; this is one-way coloration, not a full string/body feedback simulation. The bar and bell parameters are designed approximations, not measurements of a particular instrument. They are a foundation for improving realism through code and listening.

### Guitar

A blend of triangular string displacement, seeded noise, and fundamental excitation is shaped by pluck position and brightness. It enters a feedback loop containing a delay and passive filters. Its recurrence is:

```text
y[n] = excitation[n] + c0*y[n-D] + c1*y[n-D-1] + c2*y[n-D-2]
```

The three coefficients combine a damping filter and fractional-delay interpolation. Their sum is less than one, preventing energy growth. The phase of both filters is included when calculating delay length, preserving the fundamental's tuning across sample rates. Decay control targets a 60 dB fall at the fundamental, subject to losses in the passive filters; high notes can decay faster than requested.

The generated excitation depends on the score seed, track name, and note index. Editing unrelated tracks does not change it. Pluck position is a simplified comb shaping operation on the excitation, not a full geometric string simulation. The preset is intended primarily for guitar-like registers, approximately E2–E6.

### Marimba and bell

Each resonance follows a damped sinusoid:

```text
mode(t) = amplitude * sin(2*pi*frequency*t) * exp(-ln(1000)*t/decay_seconds)
```

The output sums several modes with different frequencies and lifetimes. Marimba's higher resonances disappear quickly; bell uses non-integer ratios, weakly split resonances, and longer decay. Modes fade smoothly as they approach Nyquist. Brightness and strike velocity control upper-mode amplitudes. These presets are modal approximations rather than spatial finite-element simulations.

Marimba drives each damped mode with a finite raised-cosine force, `F(t) = (1 - cos(2*pi*t/T))/T` for `0 <= t <= T`, zero otherwise. The response is the analytic convolution of this unit-area force with the damped sinusoid above. Longer, softer contact suppresses upper resonances and changes their phase; shorter, harder contact admits more high-frequency energy. Contact ends completely, after which each mode rings freely. Integration happens before sampling, preserving even sub-sample strikes. Contact is capped at 0.65 fundamental periods to retain the treble fundamental. Bell retains its exponential onset ramp. Neither model solves nonlinear mallet/bar feedback.

## Piano and bowed strings

### Piano unisons

At and above 65 Hz, each piano partial uses a small complex linear system for
its two or three detuned strings. The diagonal contains angular frequency and
intrinsic loss; a shared rank-one damping term represents a resistive bridge.
Intrinsic loss is 28% of the designed damping and common bridge loss is 72%.
These are design coefficients, not measurements of a piano. The Hermitian part
is negative definite, so free string energy cannot grow.

The eigenmodes are evaluated analytically. A finite raised-cosine hammer pulse
excites the coupled system from rest; complex modal residues retain both response
quadratures. Common motion loses energy faster than differential motion, while
slight mistuning connects them. See Julius O. Smith's
[coupled strings discussion](https://www.dsprelated.com/freebooks/pasp/Coupled_Strings.html)
and [bridge coupling analysis](https://www.dsprelated.com/freebooks/pasp/Two_Coupled_Strings.html).

Unison spread is ±0.6 cents for two strings and −0.9/0/+0.9 cents for three.
The voice also models partial stiffness, hammer contact/position filtering,
brightness and velocity response, generated contact noise and a designed
soundboard response. Below 65 Hz the single-string register uses a prescribed
two-component decay. `decay_seconds` sets a nominal decay scale, not an exact
silence time or measured whole-instrument T60.

This is a narrow-band approximation. It does not solve nonlinear hammer/string
contact, reactive bridge tuning, cross-note sympathetic resonance, longitudinal
waves or coupling between vibration planes. Piano's [binary sustain pedal](piano-sustain.md)
extends independent note gates; it does not add those physical interactions.

### Bowed excitation and body response

Violin, viola, cello and double bass use instrument-specific harmonic sources,
noise, onset envelopes and designed body bands. The excitation rolloff follows
absolute frequency with a corner bandwidth of `900 + 6500 * brightness²` Hz;
brightness includes the velocity contribution. This approximates a rounded
bridge-force waveform, without solving nonlinear bow stick/slip. See Jim
Woodhouse's [bowed-string overview](https://euphonics.org/11-3-0-summary-of-bowed-string-behaviour/)
and the [Woodhouse/Galluzzo physics review](https://euphonics.org/wp-content/uploads/2022/03/BowedStringReview.pdf).

Each body band is a damped bandpass resonance with a center frequency,
half-power bandwidth and peak gain. Its complex response colors both magnitude
and phase at each nominal harmonic. This is a steady-state response with a
prescribed onset, not a coupled body transient or measured admittance. Bow
position, force-dependent friction, wolf notes and ensembles are outside the model.
Optional [soft and accented articulations](articulations.md) alter harmonic buildup,
onset noise and source release; they do not simulate those bow mechanics.

## Score controls

```json
{
  "name": "Fingerpicked guitar",
  "instrument": "guitar",
  "tone": {"brightness": 0.6, "decay_seconds": 3.5, "pluck_position": 0.18},
  "notes": [{"pitch": "E3", "start": 0, "duration": 4, "velocity": 0.7}]
}
```

- `brightness`: 0–1, default 0.5. Changes excitation and damping for guitar; changes upper-mode amplitudes for marimba/bell.
- `decay_seconds`: 0.1–20. Defaults to 3 for guitar, 1.4 for marimba, and 5 for bell. It describes the model's natural decay, not the note's score duration.
- `pluck_position`: for the guitar model described here, 0.05–0.45 of string length; default 0.22. Smaller values are closer to the bridge. Other plucked voices expose the same control with instrument-specific defaults.
- `velocity`: controls amplitude and also contributes to brightness.

`Tone` is exported by the Python package. Supplying tone controls on basic synth voices is rejected. Supplying pluck position on a bar or bell is rejected, so agents do not receive silently ignored settings.

By default, note duration still gates the voice and its fade. A long natural decay
setting alone does not extend a short note. Optional track/note `release_seconds`
continues the generated voice under a cosine fade after note-off, and the renderer
allocates its tail automatically. Gain/pan automation, tempo changes, generated
delay and algorithmic reverb are described in [the expressive engine guide](expressive-engine.md).
This renderer release is not a physical damper or excitation transition. The optional
[bowed/wind articulations](articulations.md) add designed harmonic and noise decay
at note-off while retaining that renderer fade. Sustain
pedal, continuous tone/pitch expression and sympathetic-string coupling remain
outside these models.

The new voices extend the version-1 preset vocabulary and `tone` is optional. Existing scores remain valid. Older engine builds reject the new preset names and field. MIDI maps to approximate General MIDI nylon guitar, marimba, and tubular bell programs; it does not encode the model or tone parameters.

## Reproduce and check

Run `uv run python examples/physical_instruments.py`, then open `output/physical-instruments/index.html`. The first two clips use the same score through the original `pluck` voice and the new `guitar` voice. The next clips demonstrate marimba and bell. Each includes JSON, MIDI, WAV, and a render report.

Tests check string tuning across E2, A3, and E5 at 22050/44100/48000 Hz (less than five cents error), stability, endpoints, repeatability, decay behavior, brightness, velocity-dependent timbre, score validation, and MIDI mapping. These checks establish numerical behavior, not perceptual realism. Auditioning and comparison with real acoustic behavior remain necessary.

For piano and bowed-string changes, also run:

```sh
uv run pytest tests/test_instrument_refinement.py tests/test_finite_strikes.py tests/test_orchestra.py
```

These checks cover coupled-string integration, passive damping, tuning across
registers, brightness and velocity behavior, seeded equivalence and long/short
notes. Listen to attacks, decays and register balance before making realism claims.

## References

The implementation is original code informed by established synthesis methods:

- Julius O. Smith III, [Physical Audio Signal Processing](https://www.dsprelated.com/freebooks/pasp/): digital waveguides, damping, and modal representations.
- Ben Lynn, [The Karplus-Strong Algorithm](https://xenon.stanford.edu/~blynn/sound/karplusstrong.html): loop filtering and pitch compensation.

Further development should focus on instrument mechanics: string stiffness and body coupling, hammer interactions, reed/breath excitation, bow friction, and continuous performance controls.
